import requests
import json
import re
import time
import pickle
import os.path
import base64
import sys

###################################################################

class InstagramStoryScraper:
    
    def __init__(self):
        """ Initialize """

        self.headers = {
            'x-ig-app-id': '936619743392459',
            'x-asbd-id': '198387',
            'x-ig-www-claim': '0',
            'origin': 'https://www.instagram.com',
            'accept': '*/*',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36',
        }

        self.proxies = {
            'http': '',
            'https': '',
        }

        self.ig_story_regex = r'https?://(?:www\.)?instagram\.com/stories/([^/]+)(?:/(\d+))?/?'

        self.ig_highlights_regex = r'(?:https?://)?(?:www\.)?instagram\.com/s/(\w+)\?story_media_id=(\d+)_(\d+)'

        self.ig_session = requests.Session()


    def set_proxies(self, http_proxy: str, https_proxy: str) -> None:
        """ set proxy  """

        self.proxies['http'] = http_proxy 
        self.proxies['https'] = https_proxy


    def get_username_storyid(self, ig_story_url: str):
        """ username can be 'highlights', if 'highlights' is the username, 
            story_id will be used """

        if '/s/' in ig_story_url:
            # this is for highlights alternative URL format
            # www.instagram.com/s/<code>?story_media_id=<digits>_<digits>
            # base64 decoding of <code>
            code = re.match(self.ig_highlights_regex, ig_story_url).group(1)
            
            return {'username':'highlights', 'story_id':str(base64.b64decode(code)).split(':')[1][:-1]} 

        match = re.match(self.ig_story_regex, ig_story_url)
        if match:
            username = match.group(1)
            story_id = match.group(2)
            if story_id == None:
                # if the url does not have story id, create one just for the filename
                story_id = '3446487468465775665'
        else:
            raise SystemExit('error getting username')

        return username, story_id


    def get_userid_by_username(self, username: str, story_id: str) -> str:
        """ get the user id by username 
            if the regex extract highlights as username use story_id,
            otherwise use the username to get the user_id """

        if username == 'highlights':
            return f'highlight:{story_id}' # w/highlights user id is not necesary
        else:
            try:
                user_id = self.ig_session.get(f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}", 
                                        headers=self.headers, 
                                        proxies=self.proxies,
                                        allow_redirects=False).json()['data']['user']['id']
            except Exception as e:
                print(e, "\nError on line {}".format(sys.exc_info()[-1].tb_lineno))
                raise SystemExit('error getting user id')

            return user_id


    def ig_login(self, your_username: str, your_password: str, cookies_path: str) -> None:
        """ this perform instagram login if you dont have the cookies yet
            this method return None but get the cookies in session and save it in a file for future uses """

        if self.ig_cookies_exist(cookies_path):
            print('loading saved cookies')
            return

        ig_login_page = self.ig_session.get('https://www.instagram.com/accounts/login', headers=self.headers, proxies=self.proxies)

        try:
            csrf_token_regex = re.search(r'"csrf_token":"(\w+)"', ig_login_page.text)
            csrf_token = json.loads( '{' + csrf_token_regex.group(0) + '}' )['csrf_token']

            rollout_hash_token_regex = re.search(r'"rollout_hash":"(\w+)"', ig_login_page.text)
            rollout_hash = json.loads( '{' + rollout_hash_token_regex.group(0) + '}' )['rollout_hash']
        except Exception as e:
            print(e, "\nError on line {}".format(sys.exc_info()[-1].tb_lineno))
            raise SystemExit('error getting csrf_token, rollout_hash')

        # prepare headers and payload for login request
        login_headers = self.headers.copy()
        login_headers['x-requested-with'] = 'XMLHttpRequest'
        login_headers['x-csrftoken'] = csrf_token
        login_headers['x-instagram-ajax'] = rollout_hash
        login_headers['referer'] = 'https://www.instagram.com/'

        login_payload = {
                'enc_password': f'#PWD_INSTAGRAM_BROWSER:0:{int(time.time())}:{your_password}',
                'username': your_username,
                'queryParams': '{}',
                'optIntoOneTap': 'false',
                'stopDeletionNonce': '',
                'trustedDeviceRecords': '{}',
            }
        
        try:
            r = self.ig_session.post('https://www.instagram.com/accounts/login/ajax/',headers=login_headers ,data=login_payload)
        except Exception as e:
            print(e, "\nError on line {}".format(sys.exc_info()[-1].tb_lineno))
            raise SystemExit('error in login')  

        # save the cookies
        with open(cookies_path, 'wb') as f:
            pickle.dump(self.ig_session.cookies, f)


    def ig_cookies_exist(self, cookies_path: str) -> bool:
        """ check if cookies exist and load it"""

        if os.path.isfile(cookies_path):
            with open(cookies_path, 'rb') as f:
                self.ig_session.cookies.update(pickle.load(f))
            return True

        return False


    def get_ig_stories_urls(self, user_id: str) -> tuple:
        """ this function only can be used if you have the cookies from login """

        ig_stories_endpoint = f'https://i.instagram.com/api/v1/feed/reels_media/?reel_ids={user_id}'
        try:
            ig_url_json = self.ig_session.get(ig_stories_endpoint, headers=self.headers, proxies=self.proxies).json()
        except Exception as e:
            print(e, "\nError on line {}".format(sys.exc_info()[-1].tb_lineno))
            raise SystemExit('error getting stories json')

        stories_urls = []
        thumbnail_urls = []
        try:
            for item in ig_url_json['reels'][f'{user_id}']['items']:
                if 'video_versions' in item:
                    stories_urls.append(item['video_versions'][0]['url'])
                    thumbnail_urls.append(item['image_versions2']['candidates'][0]['url'])
                else:
                    stories_urls.append(item['image_versions2']['candidates'][0]['url'])
                    thumbnail_urls.append(item['image_versions2']['candidates'][0]['url'])
        except Exception as e:
            print(e, "\nError on line {}".format(sys.exc_info()[-1].tb_lineno))
            raise SystemExit('error getting stories urls')

        return stories_urls, thumbnail_urls


    def download(self, stories_urls_list: list) -> list:
        """ download stories """

        downloaded_item_list = []
        for story_url in stories_urls_list:
            try:
                story_request = self.ig_session.get(story_url, headers=self.headers, proxies=self.proxies, stream=True)
            except Exception as e:
                print(e, "\nError on line {}".format(sys.exc_info()[-1].tb_lineno))
                raise SystemExit('error downloading story')

            filename = story_url.split('?')[0].split('/')[-1]

            path_filename = f'{filename}'
            try:
                with open(path_filename, 'wb') as f:
                    for chunk in story_request.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)
                            f.flush()

                downloaded_item_list.append(path_filename)
            except Exception as e:
                print(e, "\nError on line {}".format(sys.exc_info()[-1].tb_lineno))
                raise SystemExit('error writting story')

        return downloaded_item_list


    def get_story_filesize(self, video_url_list: list) -> str:
        """ get file size of requested video """

        items_filesize = []
        for video_url in video_url_list:
            try:
                video_size = self.ig_session.head(video_url, headers={"Content-Type":"text"}, proxies=self.proxies)
                items_filesize.append(video_size.headers['content-length'])
            except Exception as e:
                print(e, "\nError on line {}".format(sys.exc_info()[-1].tb_lineno))
                raise SystemExit('error getting file size')

        return items_filesize


###################################################################

if __name__ == "__main__":

    # use case example

    # set your ig username and password
    your_username = 'your ig username'
    your_password = 'your ig password'

    cookies_path = 'ig_cookies'

    # set ig stories url (this only works for stories and highlights)
    # for post, reels, igtv see InstagramPostScraper class
    ig_story_url = 'your ig story/highlight url'
 
    # create scraper stories object    
    ig_story = InstagramStoryScraper()

    # set the proxy (optional, u can run it with ur own ip),
    ig_story.set_proxies('', '')

    # get the username and story id by url
    username, story_id = ig_story.get_username_storyid(ig_story_url)

    # get the user id or highlights id
    user_id = ig_story.get_userid_by_username(username, story_id)

    # perform login or load cookies
    ig_story.ig_login(your_username, your_password, cookies_path)

    # get the stories urls (sequential with get_story_filesize)
    stories_urls, thumbnail_urls = ig_story.get_ig_stories_urls(user_id)

    # get the video filesize (sequential with get_ig_stories_urls)
    #storysize = ig_story.get_story_filesize(stories_urls)
    #[print('filesize: ~' + filesize + ' bytes') for filesize in storysize]

    # download the stories
    ig_story.download(stories_urls)

    ig_story.ig_session.close()


