#!/usr/bin/env python3
"""
Re-sort all frozen news JSON files by relevance_score (descending).
This ensures agents see the most relevant articles first.
"""

import json
from pathlib import Path

CACHE_DIR = Path(__file__).parent.parent / "cache" / "news"

def resort_file(json_path: Path):
    """Sort articles by relevance_score (descending) and rewrite file."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        articles = data.get("articles", [])
        if not articles:
            return 0, 0
        
        # Sort by relevance_score descending
        articles_sorted = sorted(
            articles,
            key=lambda a: float(a.get("relevance_score", 0)),
            reverse=True
        )
        
        data["articles"] = articles_sorted
        
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return 1, len(articles)
    
    except Exception as e:
        print(f"❌ Error processing {json_path}: {e}")
        return 0, 0


def main():
    if not CACHE_DIR.exists():
        print(f"❌ Cache directory not found: {CACHE_DIR}")
        return
    
    json_files = list(CACHE_DIR.glob("*/*.json"))
    
    print("=" * 60)
    print("  RE-SORTING FROZEN NEWS BY RELEVANCE")
    print("=" * 60)
    print(f"  Found: {len(json_files)} JSON files\n")
    
    if not json_files:
        print("❌ No JSON files found!")
        return
    
    total_files = 0
    total_articles = 0
    
    for json_path in json_files:
        files, articles = resort_file(json_path)
        if files:
            total_files += files
            total_articles += articles
            ticker = json_path.parent.name
            date = json_path.stem
            print(f"  ✅ {ticker}/{date} — {articles} articles sorted")
    
    print(f"\n{'=' * 60}")
    print(f"  COMPLETE")
    print(f"  Files sorted:    {total_files}")
    print(f"  Total articles:  {total_articles}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
