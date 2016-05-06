import zlib

import pytest
import requests

from pytest_vts import vts


@pytest.fixture
def vts_rec_on(request, tmpdir):
    rec = vts(request, tmpdir)
    rec.tmpdir = tmpdir
    return rec


@pytest.fixture
def github_url():
    return "https://api.github.com/search/repositories?q=user:bhodorog"


@pytest.fixture
def github_search(github_url):
    resp = requests.get(
        github_url, headers={"Accept": "application/vnd.github.v3+json"})
    return resp


@pytest.fixture
def record_cassette(vts_rec_on, github_url):
    github_search(github_url)
    return vts_rec_on


def test_vts_recording(vts_rec_on, github_url):
    resp = github_search(github_url)
    assert resp.status_code == 200
    assert vts_rec_on.responses
    assert vts_rec_on.responses.calls
    assert vts_rec_on.responses.calls[0]
    assert vts_rec_on.responses.calls[0].request.url == github_url
    assert vts_rec_on.responses.calls[0].response
    assert vts_rec_on.cassette
    assert len(vts_rec_on.cassette) == 1
    track = vts_rec_on.cassette[0]
    assert track["request"]
    assert track["request"]["method"] == "GET"
    assert track["request"]["url"] == github_url
    assert "Accept" in track["request"]["headers"]
    assert track["request"]["body"] is None
    assert track["response"]
    assert track["response"]["status_code"] == 200
    assert track["response"]["headers"]
    assert track["response"]["headers"]["Server"] == "GitHub.com"
    assert track["response"]["body"]


def test_unrecorded_http_call(record_cassette):
    record_cassette.setup_playback()
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.get("https://circleci.com")


@pytest.mark.parametrize("url", [
    "illegal_url",
    "http://illegal.host.name/admin/",
])
def test_vts_illegal_urls(vts, url):
    with pytest.raises(requests.exceptions.RequestException):
        requests.get(url)


@pytest.mark.parametrize("poison_test_name", ["/some/path/like/name"])
def test_cassette_is_always_file(record_cassette, poison_test_name):
    cassette_dirname = record_cassette._cass_file().dirname
    assert record_cassette._cass_dir() == cassette_dirname


def test_recording_gzipped_responses_as_text(vts_rec_on, httpserver):
    data = "Hello!"
    # http://stackoverflow.com/a/22310760
    gzip_compressor = zlib.compressobj(9, zlib.DEFLATED, zlib.MAX_WBITS | 16)
    gzipped = gzip_compressor.compress(data) + gzip_compressor.flush()
    httpserver.serve_content(
        gzipped, 200,
        headers={"Content-Encoding": "gzip"})
    url = "{}/".format(httpserver.url)
    resp = requests.get(url)
    assert resp.status_code == 200
    assert resp.text == data
    assert len(vts_rec_on.cassette) == 1
    track = vts_rec_on.cassette[0]
    assert track['request']['url'] == url
    assert "Content-Encoding" not in track['response']['headers']
    assert track['response']['body'] == data


# enable pytester fixture which allows running pytests within tests
pytest_plugins = "pytester"


def test_not_saving_cassette_when_it_fails(testdir):
    testdir.makepyfile("""
        import requests

        def test_always_failing(vts):
            requests.get("https://api.github.com/search/repositories?q=user:bhodorog")
            assert False
    """)
    testdir.plugins.append("pytest-vts")
    testdir.runpytest()
    cassettes_dir = testdir.tmpdir.join("cassettes")
    assert not cassettes_dir.check()


def test_saving_cassette_when_it_passes(testdir):
    testdir.makepyfile("""
        import requests

        def test_always_passes(vts):
            requests.get("https://api.github.com/search/repositories?q=user:bhodorog")
            assert True
    """)
    testdir.plugins.append("pytest-vts")
    testdir.runpytest()
    cassettes_dir = testdir.tmpdir.join("cassettes")
    assert cassettes_dir.check()
    assert list(cassettes_dir.visit("*.cassette"))