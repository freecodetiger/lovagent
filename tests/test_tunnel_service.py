import unittest

from app.services.tunnel_service import (
    extract_quick_tunnel_url,
    is_invalid_autodetected_tunnel_url,
    is_quick_tunnel_url,
)


class TunnelServiceParsingTests(unittest.TestCase):
    def test_extract_quick_tunnel_url_returns_trycloudflare_domain(self):
        line = "Visit it at https://demo-name.trycloudflare.com and keep this terminal open."
        self.assertEqual(
            extract_quick_tunnel_url(line),
            "https://demo-name.trycloudflare.com",
        )

    def test_extract_quick_tunnel_url_ignores_reference_links(self):
        line = "See https://github.com/quic-go/quic-go/wiki/UDP-Buffer-Sizes for details."
        self.assertEqual(extract_quick_tunnel_url(line), "")
        self.assertTrue(is_invalid_autodetected_tunnel_url("https://github.com"))

    def test_is_quick_tunnel_url_requires_trycloudflare_host(self):
        self.assertTrue(is_quick_tunnel_url("https://demo-name.trycloudflare.com"))
        self.assertFalse(is_quick_tunnel_url("https://github.com"))


if __name__ == "__main__":
    unittest.main()
