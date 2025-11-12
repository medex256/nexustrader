# In nexustrader/backend/app/tools/news_tools.py
from pygooglenews import GoogleNews

def search_news(query: str, limit: int = 5):
    """
    Searches Google News for recent articles matching the query.
    """
    print(f"Searching for news about {query}...")
    gn = GoogleNews()
    search = gn.search(query)
    
    articles = []
    for item in search['entries'][:limit]:
        article = {
            "title": item.title,
            "link": item.link,
            "published": item.published,
        }
        articles.append(article)
        
    return articles

