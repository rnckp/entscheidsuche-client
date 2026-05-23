"""
Example usage of the entscheidsuche package.
"""

from entscheidsuche import EntscheidsucheClient


def main() -> None:
    """Demonstrate basic usage of the entscheidsuche API client."""
    with EntscheidsucheClient() as client:
        # Search for court decisions
        results = client.search("Mietvertrag", size=5)
        print(f"Found {results.total} results for 'Mietvertrag'\n")

        for hit in results.hits:
            print(f"📄 {hit.signatur}")
            print(f"   Date: {hit.date}")
            print(f"   Language: {hit.language}")
            title = hit.title.get("de", "")
            if title:
                print(f"   Title: {title[:70]}...")
            print()


if __name__ == "__main__":
    main()
