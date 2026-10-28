"""Thunderstore's documented multipart upload and background submission protocol.

Matches thunderstore-io/Thunderstore builder/src/api/packageSubmit.ts and
django/thunderstore/usermedia/api/experimental/serializers/upload.py.
Credentials go only to the fixed API origin, never the signed storage URLs.
"""
import base64
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = 'https://thunderstore.io/api/experimental/'
USER_AGENT = 'ApexMapPublisher/1.0 (+https://github.com/taskinoz/apex-to-titanfall-2)'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def api(path, token, data=None):
    if path.startswith('/') or '..' in path or '://' in path:
        raise ValueError('API path must be relative to the fixed Thunderstore origin')
    req = urllib.request.Request(BASE+path, data=None if data is None else json.dumps(data).encode(),
        headers={'Authorization': 'Bearer '+token, 'Content-Type': 'application/json',
                 'User-Agent': USER_AGENT, 'Cache-Control': 'no-cache'})
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'Thunderstore API {path.split("/")[0]} returned HTTP {e.code}') from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError('Thunderstore API connection failed; no credential or upload URL logged') from None


def upload_part(path, part):
    if urllib.parse.urlsplit(part['url']).scheme != 'https':
        raise ValueError('Storage upload must use HTTPS')
    with Path(path).open('rb') as f:
        f.seek(part['offset'])
        content = f.read(part['length'])
    if len(content) != part['length']:
        raise ValueError('Upload part exceeds file')
    md5 = base64.b64encode(hashlib.md5(content, usedforsecurity=False).digest()).decode()
    request = urllib.request.Request(part['url'], data=content, method='PUT',
        headers={'Content-MD5': md5, 'Content-Type': 'application/octet-stream', 'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            etag = response.headers.get('ETag')
            if not etag:
                raise RuntimeError('Storage did not return an upload part ETag')
            return {'ETag': etag, 'PartNumber': part['part_number']}
    except (urllib.error.URLError, TimeoutError):
        # A presigned URL is an ephemeral credential: never include it in errors.
        raise RuntimeError('Storage part upload failed; signed URL withheld') from None


def submit(path, namespace, token):
    path = Path(path)
    data = api('usermedia/initiate-upload/', token,
               {'filename': path.name, 'file_size_bytes': path.stat().st_size})
    uuid = data['user_media']['uuid']
    parts = sorted(data['upload_urls'], key=lambda p: p['offset'])
    end = 0
    finished = False
    try:
        for p in parts:
            if p['offset'] != end or not 0 < p['length'] <= 128*1024*1024:
                raise ValueError('Invalid or overlapping server part ranges')
            end += p['length']
        if end != path.stat().st_size:
            raise ValueError('Server upload ranges do not cover file')
        completed = []
        for part in parts:
            completed.append(upload_part(path, part))
            print(f'Uploaded {path.name}: part {len(completed)}/{len(parts)}', flush=True)
        api(f'usermedia/{uuid}/finish-upload/', token, {'parts': completed})
        finished = True
    finally:
        if not finished:
            try:
                api(f'usermedia/{uuid}/abort-upload/', token, {})
            except RuntimeError:
                pass
    submission = api('submission/submit-async/', token, {
        'upload_uuid': uuid, 'author_name': namespace, 'communities': ['northstar'],
        'community_categories': {'northstar': []}, 'has_nsfw_content': False})
    submission_id = submission['id']
    print('Background validation submitted:', path.name, submission_id, flush=True)
    deadline = time.monotonic()+1800
    while submission['status'] != 'FINISHED':
        if time.monotonic() > deadline:
            raise RuntimeError('Submission remains pending; inspect this ID before retrying: '+submission_id)
        time.sleep(5)
        submission = api(f'submission/poll-async/{submission_id}/?ci={time.time_ns()}', token)
    if submission.get('form_errors'):
        raise RuntimeError('Thunderstore validation failed: '+json.dumps(submission['form_errors'])[:1500])
    if submission.get('task_error') or not submission.get('result'):
        raise RuntimeError('Thunderstore background task failed; submission ID: '+submission_id)
    print('Published:', submission['result']['package_version']['download_url'], flush=True)
    return submission
