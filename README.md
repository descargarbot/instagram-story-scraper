# instagram story and highlights scraper
<div align="center">
  
![DescargarBot](https://www.descargarbot.com/v/download-github_instagram.png)
  
[![TikTok](https://img.shields.io/badge/on-descargarbot?logo=github&label=status&color=green
)](https://github.com/descargarbot/instagram-story-scraper/issues "Instagram Story")
</div>

<h2>dependencies</h2>
<code>Python 3.9+</code>
<code>requests</code>
<br>
<br>
<h2>install dependencies</h2>
<ul>
<li><h3>requests</h3></li>
  <code>pip install requests</code><br>
  <code>pip install -U 'requests[socks]'</code>
  <br>
<br>
</ul>
<h2>use case example</h2>

    #import the class InstagramStoryScraper
    from instagram_stories_scraper import InstagramStoryScraper

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

  or you can use the CLI
  <br><br>
  <code>python3 instagram_stories_scraper.py --username your_username --password your_password IG_URL</code>
<br><br>

>[!WARNING]\
>Accounts used with the scraper are quite susceptible to suspension. <b>Do not use your personal account</b>.<br><br>
>And when u run this scraper from a datacenter (even smaller ones), chances are large you will not pass. Also, if your ip reputation at home is low, you won't pass
 <br>
<h2>online</h2>
<ul>
  ⤵
  <li> web 🤖 <a href="https://descargarbot.com" >  DescargarBot.com</a></li>
  <li> <a href="https://t.me/xDescargarBot" > Telegram Bot 🤖 </a></li>
  <li> <a href="https://discord.gg/gcFVruyjeQ" > Discord Bot 🤖 </a></li>
</ul>

