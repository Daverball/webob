import warnings

import pytest

from webob.response import Response
from webob.util import (
    _merge_paths,
    _remove_dot_segments,
    urljoin,
    warn_deprecation,
)


class Test_warn_deprecation:
    def setup_method(self, method):
        self.oldwarn = warnings.warn
        warnings.warn = self._warn
        self.warnings = []

    def tearDown(self):
        warnings.warn = self.oldwarn
        del self.warnings

    def _callFUT(self, text, version, stacklevel):
        return warn_deprecation(text, version, stacklevel)

    def _warn(self, text, type, stacklevel=1):
        self.warnings.append(locals())

    def test_multidict_update_warning(self):
        # test warning when duplicate keys are passed
        r = Response()
        r.headers.update([("Set-Cookie", "a=b"), ("Set-Cookie", "x=y")])
        assert len(self.warnings) == 1
        deprecation_warning = self.warnings[0]
        assert deprecation_warning["type"] == UserWarning
        assert "Consider using .extend()" in deprecation_warning["text"]

    def test_multidict_update_warning_unnecessary(self):
        # no warning on normal operation
        r = Response()
        r.headers.update([("Set-Cookie", "a=b")])
        assert len(self.warnings) == 0

    def test_warn_deprecation(self):
        v = "1.3.0"

        pytest.raises(DeprecationWarning, warn_deprecation, "foo", v[:3], 1)

    def test_warn_deprecation_future_version(self):
        v = "9.9.9"

        warn_deprecation("foo", v[:3], 1)
        assert len(self.warnings) == 1


RFC3986_BASE = "http://a/b/c/d;p?q"


@pytest.mark.parametrize(
    "reference, expected",
    [
        # RFC 3986 section 5.4.1, normal examples
        ("g:h", "g:h"),
        ("g", "http://a/b/c/g"),
        ("./g", "http://a/b/c/g"),
        ("g/", "http://a/b/c/g/"),
        ("/g", "http://a/g"),
        ("//g", "http://g"),
        ("?y", "http://a/b/c/d;p?y"),
        ("g?y", "http://a/b/c/g?y"),
        ("#s", "http://a/b/c/d;p?q#s"),
        ("g#s", "http://a/b/c/g#s"),
        ("g?y#s", "http://a/b/c/g?y#s"),
        (";x", "http://a/b/c/;x"),
        ("g;x", "http://a/b/c/g;x"),
        ("g;x?y#s", "http://a/b/c/g;x?y#s"),
        ("", "http://a/b/c/d;p?q"),
        (".", "http://a/b/c/"),
        ("./", "http://a/b/c/"),
        ("..", "http://a/b/"),
        ("../", "http://a/b/"),
        ("../g", "http://a/b/g"),
        ("../..", "http://a/"),
        ("../../", "http://a/"),
        ("../../g", "http://a/g"),
        # RFC 3986 section 5.4.2, abnormal examples
        ("../../../g", "http://a/g"),
        ("../../../../g", "http://a/g"),
        ("/./g", "http://a/g"),
        ("/../g", "http://a/g"),
        ("g.", "http://a/b/c/g."),
        (".g", "http://a/b/c/.g"),
        ("g..", "http://a/b/c/g.."),
        ("..g", "http://a/b/c/..g"),
        ("./../g", "http://a/b/g"),
        ("./g/.", "http://a/b/c/g/"),
        ("g/./h", "http://a/b/c/g/h"),
        ("g/../h", "http://a/b/c/h"),
        ("g;x=1/./y", "http://a/b/c/g;x=1/y"),
        ("g;x=1/../y", "http://a/b/c/y"),
        ("g#s/./x", "http://a/b/c/g#s/./x"),
        ("g#s/../x", "http://a/b/c/g#s/../x"),
        # Like urllib.parse.urljoin(), use the non-strict (backwards
        # compatible) variant of RFC 3986 5.2.2: a reference with the same
        # scheme as the base is treated as relative. A strict parser would
        # return "http:g" here.
        ("http:g", "http://a/b/c/g"),
        ("HTTP:g", "http://a/b/c/g"),
    ],
)
def test_urljoin_rfc3986_reference_resolution(reference, expected):
    # The examples from RFC 3986 section 5.4
    assert urljoin(RFC3986_BASE, reference) == expected


@pytest.mark.parametrize(
    "reference, expected",
    [
        # urllib.parse.urljoin() removes ASCII tab/CR/LF anywhere in the
        # URL and strips leading/trailing C0 control and space characters
        # before parsing, which can promote a relative path to a
        # protocol-relative or absolute URL. WebOb's urljoin() must treat
        # those characters like any other character. See
        # GHSA-6hx8-3wjj-gr8g, GHSA-fh3h-vg37-cc95, and CVE-2024-42353.
        (" //www.example.com/test", "http://a/b/c/ //www.example.com/test"),
        ("\t//www.example.com/test", "http://a/b/c/\t//www.example.com/test"),
        ("\n//www.example.com/test", "http://a/b/c/\n//www.example.com/test"),
        ("\r//www.example.com/test", "http://a/b/c/\r//www.example.com/test"),
        ("\x00//www.example.com/test", "http://a/b/c/\x00//www.example.com/test"),
        ("\x1f//www.example.com/test", "http://a/b/c/\x1f//www.example.com/test"),
        ("/\t/www.example.com/test", "http://a/\t/www.example.com/test"),
        ("/\r\n/www.example.com/test", "http://a/\r\n/www.example.com/test"),
        (" http://www.example.com/test", "http://a/b/c/ http://www.example.com/test"),
        (
            "\thttps://www.example.com/test",
            "http://a/b/c/\thttps://www.example.com/test",
        ),
        (
            "https\t://www.example.com/test",
            "http://a/b/c/https\t://www.example.com/test",
        ),
    ],
)
def test_urljoin_does_not_strip_whitespace(reference, expected):
    assert urljoin(RFC3986_BASE, reference) == expected


@pytest.mark.parametrize(
    "base, reference, expected",
    [
        # authority with an empty path
        ("http://a", "g", "http://a/g"),
        # empty authority
        ("http://a/b", "///g", "http:///g"),
        # base without an authority
        (
            "mailto:user@example.com",
            "another@example.com",
            "mailto:another@example.com",
        ),
        # base without a scheme
        ("//a/b/c", "g", "//a/b/g"),
        # reference with an authority and a path
        ("http://a/b/c", "//g/x/../y?q#f", "http://g/y?q#f"),
        # a colon in the first segment of a relative path is parsed as a
        # scheme, as in urllib.parse.urljoin(); use "./" to avoid that
        ("http://a/b/c", "g:x/y", "g:x/y"),
        ("http://a/b/c", "./g:x/y", "http://a/b/g:x/y"),
        # invalid scheme (must start with ALPHA) means a relative path
        ("http://a/b/c", "0http://evil.example", "http://a/b/0http://evil.example"),
        # empty fragment and query are preserved
        ("http://a/b/c", "g?", "http://a/b/g?"),
        ("http://a/b/c", "g#", "http://a/b/g#"),
        # base query/fragment are dropped when the reference has a path
        ("http://a/b/c?q#f", "g", "http://a/b/g"),
        # base fragment is never inherited
        ("http://a/b/c#f", "", "http://a/b/c"),
    ],
)
def test_urljoin_component_edge_cases(base, reference, expected):
    assert urljoin(base, reference) == expected


@pytest.mark.parametrize(
    "path, expected",
    [
        ("", ""),
        (".", ""),
        ("..", ""),
        ("./g", "g"),
        ("../g", "g"),
        ("/.", "/"),
        ("/..", "/"),
        ("/./g", "/g"),
        ("/../g", "/g"),
        ("/a/b/c/./../../g", "/a/g"),
        ("mid/content=5/../6", "mid/6"),
    ],
)
def test_remove_dot_segments(path, expected):
    # The examples from RFC 3986 section 5.2.4, plus relative-path edge
    # cases that urljoin() itself cannot reach with an absolute base URI
    assert _remove_dot_segments(path) == expected


def test_merge_paths_relative_base_without_slash():
    # only reachable through urljoin() with a relative, rootless base
    assert _merge_paths(None, "x", "y") == "y"
