#! /usr/bin/env python3
# Based on https://github.com/simonw/simonw/
from python_graphql_client import GraphqlClient
import feedparser
import json
import pathlib
import re
import os
import requests

root = pathlib.Path(__file__).parent.resolve()
client = GraphqlClient(endpoint="https://api.github.com/graphql")


TOKEN = os.environ.get("MTE90_TOKEN", "")


def replace_chunk(content, marker, chunk):
    r = re.compile(
        r"<!\-\- {} starts \-\->.*<!\-\- {} ends \-\->".format(marker, marker),
        re.DOTALL,
    )
    chunk = "<!-- {} starts -->\n{}\n<!-- {} ends -->".format(marker, chunk, marker)
    return r.sub(chunk, content)


def make_query(after_cursor=None):
    return """
query {
  viewer {
    repositories(first: 100, privacy: PUBLIC, after:AFTER,  orderBy: {field: UPDATED_AT, direction: DESC}, ,affiliations:[OWNER, ORGANIZATION_MEMBER, COLLABORATOR], ownerAffiliations:[OWNER, ORGANIZATION_MEMBER, COLLABORATOR]) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        nameWithOwner
        name
        releases(last:1, orderBy: {field: CREATED_AT, direction: ASC}) {
          totalCount
          nodes {
            name
            publishedAt
            url
            author {
              login
            }
          }
        }
      }
    }
  }
}
""".replace(
        "AFTER", '"{}"'.format(after_cursor) if after_cursor else "null"
    )


def fetch_releases(oauth_token):
    releases = []
    has_next_page = True
    after_cursor = None

    while has_next_page:
        data = client.execute(
            query=make_query(after_cursor),
            headers={"Authorization": "Bearer {}".format(oauth_token)},
        )
        print()
        print(json.dumps(data, indent=4))
        print()
        for repo in data["data"]["viewer"]["repositories"]["nodes"]:
            if len(repo["releases"]["nodes"]) != 0 and repo["releases"]["nodes"][0]["author"]["login"] == 'Mte90':
                releases.append(
                    {
                        "nameWithOwner": repo["nameWithOwner"],
                        "release": repo["releases"]["nodes"][0]["name"].replace(repo["name"], "").strip(),
                        "published_at": repo["releases"]["nodes"][0]["publishedAt"].replace('-','/').split("T")[0],
                        "url": repo["releases"]["nodes"][0]["url"],
                    }
                )
        has_next_page = data["data"]["viewer"]["repositories"]["pageInfo"][
            "hasNextPage"
        ]
        after_cursor = data["data"]["viewer"]["repositories"]["pageInfo"]["endCursor"]
    
    releases.sort(key=lambda r: r["published_at"], reverse=True)
    return releases


def fetch_blog_entries():
    entries = feedparser.parse("https://daniele.tech/en/feed")["entries"]
    return [
        {
            "title": entry["title"],
            "url": entry["link"].split("#")[0],
            "published": "%d/%02d/%02d" % (entry.published_parsed.tm_year, entry.published_parsed.tm_mon, entry.published_parsed.tm_mday),
        }
        for entry in entries
    ]

def fetch_reddit_pinned():
    items = []
    headers = {"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36"}
    request = requests.get("https://api.reddit.com/user/mte90?limit=25", headers=headers)
    json_response = request.json()
    for item in json_response['data']['children']:
        if 'pinned' in item['data'] and item['data']['pinned']:
            items.append(
                {
                    "title": item['data']["title"],
                    "url": item['data']['url'],
                    "sub": item['data']['subreddit_name_prefixed']
                }
            )
    return items
    
if __name__ == "__main__":
    readme = root / "README.md"
    releases = fetch_releases(TOKEN)
    md = "\n".join(
        [
            "* [{nameWithOwner} {release}]({url}) - {published_at}".format(**release)
            for release in releases[:8]
        ]
    )
    readme_contents = readme.open().read()
    rewritten = replace_chunk(readme_contents, "recent_releases", md)

    entries = fetch_blog_entries()[:5]
    entries_md = "\n".join(
        ["* [{title}]({url}) - {published}".format(**entry) for entry in entries]
    )
    rewritten = replace_chunk(rewritten, "blog", entries_md)
    
    entries = fetch_reddit_pinned()
    entries_md = "\n".join(
        ["* [{title}]({url}) - {sub}".format(**entry) for entry in entries]
    )
    rewritten = replace_chunk(rewritten, "reddit_pinned", entries_md)

    readme.open("w").write(rewritten)
