import ssl
import certifi
from django.core.mail.backends.smtp import EmailBackend


class CertifiEmailBackend(EmailBackend):
    """
    SMTP backend that uses certifi's CA bundle for TLS verification.
    Fixes SSL CERTIFICATE_VERIFY_FAILED issues on some Windows setups.
    """
    def open(self):
        if self.connection:
            return False

        # Use certifi CA bundle for TLS verification
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        return super().open()