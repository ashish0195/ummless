from __future__ import annotations

import os

from tests.helpers import complete_assessment, signup


def _first_clip(assessment: dict) -> str:
    for dim in assessment["result"]["dimensions"]:
        for moment in dim["evidence"]:
            if moment["audio_url"]:
                return moment["audio_url"]
    raise AssertionError("no clip found")


def test_signed_media_urls_and_ownership(client, audio_dir):
    owner = signup(client)
    assessment = complete_assessment(client, owner, audio_dir, activity_ids=["tell_a_story"])
    url = _first_clip(assessment)
    assert client.get(url).status_code == 200  # signed URL works without a token
    media_id = url.split("/v1/media/")[1].split("?")[0]
    unsigned = f"/v1/media/{media_id}"
    assert client.get(unsigned).status_code == 401
    assert client.get(unsigned, headers=owner).status_code == 200
    stranger = signup(client)
    assert client.get(unsigned, headers=stranger).status_code == 404
    tampered = url[:-3] + "abc"
    assert client.get(tampered).status_code == 401


def test_account_deletion_removes_everything(client, audio_dir, settings):
    headers = signup(client)
    complete_assessment(client, headers, audio_dir, activity_ids=["tell_a_story"])
    user_id = client.get("/v1/me", headers=headers).json()["user_id"]
    user_dir = os.path.join(settings.media_dir, user_id)
    assert os.path.isdir(user_dir) and os.listdir(user_dir)
    assert client.delete("/v1/me", headers=headers).status_code == 204
    assert client.get("/v1/me", headers=headers).status_code == 401
    assert not os.path.exists(user_dir)
