#! /usr/bin/env python3
# Based on https://github.com/simonw/simonw/
from python_graphql_client import GraphqlClient
import feedparser
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


def fetch_download_book():
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0"}
    request = requests.get("https://api.github.com/repos/mte90/Contribute-to-opensource-the-right-way/releases", headers=headers)
    json_response = request.json()
    total = int(json_response[0]['assets'][0]['download_count']) + int(json_response[0]['assets'][1]['download_count'])
    total = 'Latest edition total (GitHub) downloads: <h2>' + str(total) + '🎉</h2><br>!'
    return total


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

    total_book = fetch_download_book()
    rewritten = replace_chunk(rewritten, "book_stats", total_book)

    readme.open("w").write(rewritten)
