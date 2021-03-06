#
# Copyright © 2012 - 2020 Michal Čihař <michal@cihar.com>
#
# This file is part of Weblate <https://weblate.org/>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from weblate.machinery.base import MachineTranslation, MissingConfiguration

TOKEN_URL = (
    "https://{0}api.cognitive.microsoft.com/sts/v1.0/" "issueToken?Subscription-Key={1}"
)
TOKEN_EXPIRY = timedelta(minutes=9)


class MicrosoftCognitiveTranslation(MachineTranslation):
    """Microsoft Cognitive Services Translator API support."""

    name = "Microsoft Translator"

    language_map = {
        "zh-hant": "zh-CHT",
        "zh-hans": "zh-CHS",
        "zh-tw": "zh-CHT",
        "zh-cn": "zh-CHS",
        "tlh-qaak": "tlh-Qaak",
        "nb": "no",
        "bs-latn": "bs-Latn",
        "sr-latn": "sr-Latn",
        "sr-cyrl": "sr-Cyrl",
    }

    def __init__(self):
        """Check configuration."""
        super().__init__()
        self._access_token = None
        self._token_expiry = None

        # check settings for Microsoft region prefix
        if settings.MT_MICROSOFT_REGION is None:
            region = ""
        else:
            region = "{}.".format(settings.MT_MICROSOFT_REGION)

        self._cognitive_token_url = TOKEN_URL.format(
            region, settings.MT_MICROSOFT_COGNITIVE_KEY
        )

        if settings.MT_MICROSOFT_COGNITIVE_KEY is None:
            raise MissingConfiguration("Microsoft Translator requires credentials")

    @staticmethod
    def get_url(suffix):
        return "https://{}/{}".format(settings.MT_MICROSOFT_BASE_URL, suffix)

    def is_token_expired(self):
        """Check whether token is about to expire."""
        return self._token_expiry <= timezone.now()

    def get_authentication(self):
        """Hook for backends to allow add authentication headers to request."""
        return {"Authorization": "Bearer {0}".format(self.access_token)}

    @property
    def access_token(self):
        """Obtain and caches access token."""
        if self._access_token is None or self.is_token_expired():
            self._access_token = self.request(
                "post", self._cognitive_token_url, skip_auth=True
            ).text
            self._token_expiry = timezone.now() + TOKEN_EXPIRY

        return self._access_token

    def convert_language(self, language):
        """Convert language to service specific code.

        Remove second part of locale in most of cases.
        """
        return super().convert_language(language.replace("_", "-").lower())

    def download_languages(self):
        """Download list of supported languages from a service.

        Example of the response:

        ['af', 'ar', 'bs-Latn', 'bg', 'ca', 'zh-CHS', 'zh-CHT', 'yue', 'hr', 'cs', 'da',
        'nl', 'en', 'et', 'fj', 'fil', 'fi', 'fr', 'de', 'el', 'ht', 'he', 'hi', 'mww',
        'h', 'id', 'it', 'ja', 'sw', 'tlh', 'tlh-Qaak', 'ko', 'lv', 'lt', 'mg', 'ms',
        'mt', 'yua', 'no', 'otq', 'fa', 'pl', 'pt', 'ro', 'r', 'sm', 'sr-Cyrl',
        'sr-Latn', 'sk', 'sl', 'es', 'sv', 'ty', 'th', 'to', 'tr', 'uk', 'ur', 'vi',
        'cy']
        """
        response = self.request(
            "get", self.get_url("languages"), params={"api-version": "3.0"}
        )
        # Microsoft tends to use utf-8-sig instead of plain utf-8
        response.encoding = response.apparent_encoding
        payload = response.json()

        # We should get an object, string usually means an error
        if isinstance(payload, str):
            raise Exception(payload)

        return payload["translation"].keys()

    def download_translations(self, source, language, text, unit, user):
        """Download list of possible translations from a service."""
        args = {
            "api-version": "3.0",
            "from": source,
            "to": language,
            "category": "general",
        }
        response = self.request(
            "post", self.get_url("translate"), params=args, json=[{"Text": text[:5000]}]
        )
        # Microsoft tends to use utf-8-sig instead of plain utf-8
        response.encoding = response.apparent_encoding
        payload = response.json()
        yield {
            "text": payload[0]["translations"][0]["text"],
            "quality": self.max_score,
            "service": self.name,
            "source": text,
        }
