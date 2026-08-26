from __future__ import annotations

import json
import zipfile

from monitor.follow_audit import import_export_zip, parse_instagram_export


def _entry(username: str) -> dict:
    return {
        "string_list_data": [
            {
                "href": f"https://www.instagram.com/{username}",
                "value": username,
                "timestamp": 1710000000,
            }
        ]
    }


def _write_export(path, followers, following) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "followers_and_following/followers_1.json",
            json.dumps([_entry(username) for username in followers]),
        )
        archive.writestr(
            "followers_and_following/following.json",
            json.dumps(
                {
                    "relationships_following": [
                        _entry(username) for username in following
                    ]
                }
            ),
        )


def test_parse_instagram_followers_and_following_zip(tmp_path):
    export_path = tmp_path / "instagram-export.zip"
    _write_export(export_path, followers=["alice", "bob"], following=["alice", "charlie"])

    lists = parse_instagram_export(export_path)

    assert sorted(lists.followers) == ["alice", "bob"]
    assert sorted(lists.following) == ["alice", "charlie"]


def test_import_export_zip_builds_comparison_and_history(tmp_path):
    data_dir = tmp_path / "audit"
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    _write_export(first, followers=["alice", "bob"], following=["alice", "charlie"])
    _write_export(second, followers=["alice", "dora"], following=["alice", "charlie", "eve"])

    first_result = import_export_zip(data_dir, first)
    second_result = import_export_zip(data_dir, second)

    assert first_result["followers_count"] == 2
    assert first_result["following_count"] == 2
    assert first_result["not_following_back"] == [{"username": "charlie"}]
    assert first_result["fans"] == [{"username": "bob"}]
    assert second_result["new_followers"] == [{"username": "dora"}]
    assert second_result["lost_followers"] == [{"username": "bob"}]
    assert second_result["not_following_back"] == [
        {"username": "charlie"},
        {"username": "eve"},
    ]
