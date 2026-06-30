import json
import re
import os.path
import base64
import sys

from urllib.parse import urlparse, parse_qs
from curl_cffi import requests


###################################################################

class InstagramStoryScraper:

    def __init__(self, cookies_path: str = None):
        """Initialize"""

        self.cookies_path = cookies_path

        self.IG_BASE_URL = 'https://www.instagram.com'
        self.IG_API_BASE_URL = 'https://i.instagram.com/api/v1'

        self.IG_APP_ID = '936619743392459'

        self.impersonate = 'chrome120'

        self.headers = {
            'x-ig-app-id': self.IG_APP_ID,
            'x-asbd-id': '359341',
            'x-ig-www-claim': '0',
            'origin': 'https://www.instagram.com',
            'accept': '*/*',
        }

        self.proxies = {
            'http': '',
            'https': '',
        }

        self.ig_story_regex = (
            r'https?://(?:www\.)?instagram\.com/stories/'
            r'(?P<username>[^/?#]+)'
            r'(?:/(?P<story_id>\d+))?'
            r'/?(?:[?#].*)?$'
        )

        self.ig_highlights_regex = (
            r'(?:https?://)?(?:www\.)?instagram\.com/s/'
            r'(?P<code>[-\w=]+)'
            r'(?:[/?#].*)?$'
        )

        self.ig_session = requests.Session()

        self.username = None
        self.story_id = None
        self.target_story_media_id = None

        if self.cookies_path:
            self.ig_cookies_exist(self.cookies_path)

    ###################################################################

    def _get_proxies(self):
        """Return proxies only if configured"""

        proxies = {k: v for k, v in self.proxies.items() if v}
        return proxies or None

    ###################################################################

    def set_proxies(self, http_proxy: str, https_proxy: str) -> None:
        """set proxy"""

        self.proxies['http'] = http_proxy
        self.proxies['https'] = https_proxy

    ###################################################################

    def ig_cookies_exist(self, cookies_path: str = None) -> bool:
        """
        Load cookies from Netscape cookies.txt format.

        Example:
        .instagram.com    TRUE    /    TRUE    1893456000    sessionid    xxxx
        """

        cookies_path = cookies_path or self.cookies_path

        if not cookies_path or not os.path.isfile(cookies_path):
            return False

        loaded_cookies = 0

        try:
            with open(cookies_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()

                    if not line:
                        continue

                    if line.startswith('#') and not line.startswith('#HttpOnly_'):
                        continue

                    if line.startswith('#HttpOnly_'):
                        line = line[len('#HttpOnly_'):]

                    parts = line.split('\t')

                    if len(parts) < 7:
                        parts = line.split()

                    if len(parts) < 7:
                        continue

                    domain = parts[0]
                    path = parts[2]
                    name = parts[5]
                    value = parts[6]

                    if not domain or not name:
                        continue

                    self.ig_session.cookies.set(
                        name,
                        value,
                        domain=domain,
                        path=path or '/',
                    )

                    loaded_cookies += 1

            return loaded_cookies > 0

        except Exception as e:
            print(e, "\nError on line {}".format(sys.exc_info()[-1].tb_lineno))
            raise SystemExit('error loading cookies file')

    ###################################################################

    def _decode_highlight_code(self, code: str) -> str:
        """Decode instagram.com/s/<code> base64 highlight code"""

        try:
            padded_code = code + '=' * (-len(code) % 4)
            decoded = base64.urlsafe_b64decode(padded_code.encode()).decode('utf-8', errors='ignore')
            return decoded

        except Exception as e:
            print(e, "\nError on line {}".format(sys.exc_info()[-1].tb_lineno))
            raise SystemExit('error decoding highlight code')

    ###################################################################

    def _extract_highlight_id_from_code(self, code: str) -> str:
        """Extract highlight id from decoded /s/<code> URL"""

        decoded = self._decode_highlight_code(code)

        patterns = [
            r'highlight:(\d+)',
            r'highlight_id=(\d+)',
            r'reel_id=(\d+)',
            r':(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, decoded)

            if match:
                return match.group(1)

        numbers = re.findall(r'\d{8,}', decoded)

        if numbers:
            return numbers[0]

        raise SystemExit('error extracting highlight id from /s/ url')

    ###################################################################

    def get_username_storyid(self, ig_story_url: str) -> tuple:
        """
        Return username and story_id.

        username can be 'highlights'.
        If username == 'highlights', story_id is the highlight id.
        """

        ig_story_url = ig_story_url.strip()

        self.username = None
        self.story_id = None
        self.target_story_media_id = None

        # Alternative highlight URL:
        # https://www.instagram.com/s/<code>?story_media_id=<media_id>_<user_id>
        if '/s/' in ig_story_url:
            match = re.match(self.ig_highlights_regex, ig_story_url)

            if not match:
                raise SystemExit('error getting highlight code')

            code = match.group('code')
            highlight_id = self._extract_highlight_id_from_code(code)

            parsed_url = urlparse(ig_story_url)
            query = parse_qs(parsed_url.query)

            story_media_id = query.get('story_media_id', [None])[0]

            if story_media_id:
                self.target_story_media_id = story_media_id.split('_')[0]

            self.username = 'highlights'
            self.story_id = highlight_id

            return self.username, self.story_id

        match = re.match(self.ig_story_regex, ig_story_url)

        if not match:
            raise SystemExit('error getting username')

        username = match.group('username')
        story_id = match.group('story_id')

        if username == 'highlights' and not story_id:
            raise SystemExit('input URL is missing a highlight ID')

        self.username = username
        self.story_id = story_id

        # For normal stories, if URL has a story id, download only that story.
        # If URL has no story id, download all currently available stories.
        if username != 'highlights' and story_id:
            self.target_story_media_id = story_id

        return username, story_id

    ###################################################################

    def get_userid_by_username(self, username: str, story_id: str = None) -> str:
        """
        Get user id by username.

        For highlights, return highlight:<id>.
        """

        if username == 'highlights':
            if not story_id:
                raise SystemExit('missing highlight id')

            return f'highlight:{story_id}'

        headers_user_info = self.headers.copy()
        headers_user_info['referer'] = f'https://www.instagram.com/{username}/'

        try:
            response = self.ig_session.get(
                f'{self.IG_BASE_URL}/api/v1/users/web_profile_info/',
                headers=headers_user_info,
                params={
                    'username': username,
                },
                proxies=self._get_proxies(),
                impersonate=self.impersonate,
                allow_redirects=False,
            )

            data = response.json()

            user_id = (
                data
                .get('data', {})
                .get('user', {})
                .get('id')
            )

            if user_id:
                return str(user_id)

        except Exception:
            pass

        # Fallback: try to parse story page
        try:
            if story_id:
                story_url = f'{self.IG_BASE_URL}/stories/{username}/{story_id}/'
            else:
                story_url = f'{self.IG_BASE_URL}/stories/{username}/'

            response = self.ig_session.get(
                story_url,
                headers=headers_user_info,
                proxies=self._get_proxies(),
                impersonate=self.impersonate,
            )

            patterns = [
                r'"user"\s*:\s*{[^{}]*"pk"\s*:\s*"?(?P<id>\d+)',
                r'"user"\s*:\s*{[^{}]*"id"\s*:\s*"?(?P<id>\d+)',
                r'"owner"\s*:\s*{[^{}]*"id"\s*:\s*"?(?P<id>\d+)',
                r'"profile_id"\s*:\s*"?(?P<id>\d+)',
            ]

            for pattern in patterns:
                match = re.search(pattern, response.text)

                if match:
                    return match.group('id')

        except Exception:
            pass

        raise SystemExit('error getting user id. cookies may be required')

    ###################################################################

    def _int_or_none(self, value):
        """safe int conversion"""

        try:
            if value is None:
                return None
            return int(value)
        except Exception:
            return None

    ###################################################################

    def _get_version_area(self, item: dict):
        """Get media area from width/height fields"""

        width = (
            self._int_or_none(item.get('width'))
            or self._int_or_none(item.get('config_width'))
        )

        height = (
            self._int_or_none(item.get('height'))
            or self._int_or_none(item.get('config_height'))
        )

        if width and height:
            return width * height

        return None

    ###################################################################

    def _normalize_versions(self, versions: list, url_key: str = 'url') -> list:
        """normalize image/video version list"""

        if not isinstance(versions, list):
            return []

        normalized = []

        for index, item in enumerate(versions):
            if not isinstance(item, dict):
                continue

            url = item.get(url_key) or item.get('url') or item.get('src')

            if not url:
                continue

            normalized.append({
                'index': index,
                'url': url,
                'area': self._get_version_area(item),
            })

        return normalized

    ###################################################################

    def _get_best_url_from_versions(
        self,
        versions: list,
        url_key: str = 'url',
        default_order: str = 'desc',
    ) -> str:
        """
        Get highest quality URL.

        default_order:
            desc -> first item is assumed largest if dimensions are missing
            asc  -> last item is assumed largest if dimensions are missing
        """

        normalized = self._normalize_versions(versions, url_key=url_key)

        if not normalized:
            return None

        items_with_area = [item for item in normalized if item['area'] is not None]

        if items_with_area:
            return max(items_with_area, key=lambda item: item['area'])['url']

        if default_order == 'asc':
            return normalized[-1]['url']

        return normalized[0]['url']

    ###################################################################

    def _get_smallest_url_from_versions(
        self,
        versions: list,
        url_key: str = 'url',
        default_order: str = 'desc',
    ) -> str:
        """
        Get smallest quality URL, useful as thumbnail.

        default_order:
            desc -> last item is assumed smallest if dimensions are missing
            asc  -> first item is assumed smallest if dimensions are missing
        """

        normalized = self._normalize_versions(versions, url_key=url_key)

        if not normalized:
            return None

        items_with_area = [item for item in normalized if item['area'] is not None]

        if items_with_area:
            return min(items_with_area, key=lambda item: item['area'])['url']

        if default_order == 'asc':
            return normalized[0]['url']

        return normalized[-1]['url']

    ###################################################################

    def _get_item_pk(self, item: dict) -> str:
        """Get story media pk/id"""

        item_id = item.get('pk') or item.get('id')

        if item_id is None:
            return None

        return str(item_id).split('_')[0]

    ###################################################################

    def _extract_story_item_urls(self, item: dict) -> tuple:
        """Extract media URL and thumbnail URL from a story item"""

        if not isinstance(item, dict):
            return None, None

        story_url = None
        thumbnail_url = None

        video_versions = item.get('video_versions') or []

        if video_versions:
            story_url = self._get_best_url_from_versions(
                video_versions,
                url_key='url',
                default_order='desc',
            )

        image_candidates = (
            item
            .get('image_versions2', {})
            .get('candidates', [])
        )

        if image_candidates:
            image_best_url = self._get_best_url_from_versions(
                image_candidates,
                url_key='url',
                default_order='desc',
            )

            image_thumb_url = self._get_smallest_url_from_versions(
                image_candidates,
                url_key='url',
                default_order='desc',
            )

            if not story_url:
                story_url = image_best_url

            thumbnail_url = image_thumb_url

        if not thumbnail_url:
            thumbnail_url = story_url

        return story_url, thumbnail_url

    ###################################################################

    def get_ig_stories_urls(self, user_id: str) -> tuple:
        """Get stories/highlights URLs from reels_media endpoint"""

        headers_stories = self.headers.copy()
        headers_stories['referer'] = 'https://www.instagram.com/'

        csrf_token = self.ig_session.cookies.get('csrftoken')

        if csrf_token:
            headers_stories['x-csrftoken'] = csrf_token

        ig_stories_endpoint = f'{self.IG_API_BASE_URL}/feed/reels_media/?reel_ids={user_id}'

        try:
            response = self.ig_session.get(
                ig_stories_endpoint,
                headers=headers_stories,
                proxies=self._get_proxies(),
                impersonate=self.impersonate,
            )

            ig_url_json = response.json()

        except Exception as e:
            print(e, "\nError on line {}".format(sys.exc_info()[-1].tb_lineno))
            raise SystemExit('error getting stories json')

        reels = ig_url_json.get('reels') or {}

        reel_data = reels.get(str(user_id))

        if not reel_data:
            try:
                print(json.dumps(ig_url_json, indent=2, ensure_ascii=False)[:2000])
            except Exception:
                pass

            raise SystemExit('error getting stories json. cookies may be required')

        items = reel_data.get('items') or []

        if self.target_story_media_id:
            filtered_items = [
                item for item in items
                if self._get_item_pk(item) == str(self.target_story_media_id)
            ]

            if filtered_items:
                items = filtered_items
            else:
                raise SystemExit('target story item was not found')

        stories_urls = []
        thumbnail_urls = []

        try:
            for item in items:
                story_url, thumbnail_url = self._extract_story_item_urls(item)

                if story_url:
                    stories_urls.append(story_url)
                    thumbnail_urls.append(thumbnail_url)

        except Exception as e:
            print(e, "\nError on line {}".format(sys.exc_info()[-1].tb_lineno))
            raise SystemExit('error getting stories urls')

        if not stories_urls:
            raise SystemExit('no downloadable stories found')

        return stories_urls, thumbnail_urls

    ###################################################################

    def download(self, stories_urls_list: list) -> list:
        """download stories"""

        headers_download = self.headers.copy()
        headers_download['referer'] = 'https://www.instagram.com/'

        downloaded_item_list = []

        for index, story_url in enumerate(stories_urls_list, start=1):
            try:
                story_request = self.ig_session.get(
                    story_url,
                    headers=headers_download,
                    proxies=self._get_proxies(),
                    stream=True,
                    impersonate=self.impersonate,
                )

                if story_request.status_code >= 400:
                    raise SystemExit(f'HTTP {story_request.status_code} downloading story')

            except Exception as e:
                print(e, "\nError on line {}".format(sys.exc_info()[-1].tb_lineno))
                raise SystemExit('error downloading story')

            filename = story_url.split('?')[0].split('/')[-1]

            if not filename:
                filename = f'story_{index}.bin'

            path_filename = filename

            if os.path.exists(path_filename):
                root, ext = os.path.splitext(filename)

                if not ext:
                    ext = '.bin'

                path_filename = f'{root}_{index}{ext}'

            try:
                with open(path_filename, 'wb') as f:
                    for chunk in story_request.iter_content():
                        if chunk:
                            f.write(chunk)

                downloaded_item_list.append(path_filename)

            except Exception as e:
                print(e, "\nError on line {}".format(sys.exc_info()[-1].tb_lineno))
                raise SystemExit('error writing story')

        return downloaded_item_list

    ###################################################################

    def get_story_filesize(self, video_url_list: list) -> list:
        """get file size of requested story media"""

        items_filesize = []

        headers_filesize = self.headers.copy()
        headers_filesize['referer'] = 'https://www.instagram.com/'

        for video_url in video_url_list:
            try:
                video_size = self.ig_session.head(
                    video_url,
                    headers=headers_filesize,
                    proxies=self._get_proxies(),
                    impersonate=self.impersonate,
                    allow_redirects=True,
                )

                items_filesize.append(video_size.headers.get('content-length', '0'))

            except Exception as e:
                print(e, "\nError on line {}".format(sys.exc_info()[-1].tb_lineno))
                raise SystemExit('error getting file size')

        return items_filesize


###################################################################

if __name__ == "__main__":

    if len(sys.argv) < 2:
        print('usage:')
        print('python3 instagram_stories_scraper.py IG_STORY_OR_HIGHLIGHT_URL [cookies.txt]')
        exit()

    ig_story_url = sys.argv[1]

    cookies_path = None

    if len(sys.argv) >= 3:
        cookies_path = sys.argv[2]
    elif os.path.isfile('ig_cookies.txt'):
        cookies_path = 'ig_cookies.txt'

    # create scraper stories object
    ig_story = InstagramStoryScraper(cookies_path)

    # optional proxy
    # ig_story.set_proxies('<your http proxy>', '<your https proxy>')

    username, story_id = ig_story.get_username_storyid(ig_story_url)

    user_id = ig_story.get_userid_by_username(username, story_id)

    print('reel id:', user_id)

    stories_urls, thumbnail_urls = ig_story.get_ig_stories_urls(user_id)

    print('\nstory urls:')
    for url in stories_urls:
        print(url)

    print('\nthumbnail urls:')
    for url in thumbnail_urls:
        print(url)

    story_sizes = ig_story.get_story_filesize(stories_urls)

    for filesize in story_sizes:
        print('filesize: ~' + filesize + ' bytes')
    
    downloaded_files = ig_story.download(stories_urls)

    print('\ndownloaded files:')
    for file in downloaded_files:
        print(file)

    ig_story.ig_session.close()
