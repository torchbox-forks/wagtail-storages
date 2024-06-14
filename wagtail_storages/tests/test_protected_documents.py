from urllib.parse import urlparse

from django.test import TestCase
from django.urls import reverse

from moto import mock_aws

from wagtail_storages.factories import CollectionViewRestrictionFactory, DocumentFactory
from wagtail_storages.tests.base import CreateBucket
from wagtail_storages.tests.utils import is_s3_object_is_public


@mock_aws
class AmazonS3DocumentTests(CreateBucket, TestCase):
    def check_s3_url(self, url):
        return "s3.amazonaws.com" in url or "media.torchbox.com" in url

    def check_url_signed(self, url):
        parsed_url = urlparse(url)
        # Make sure query parameters match signed URL's parameters
        return all(
            query_arg in parsed_url.query
            for query_arg in {"AWSAccessKeyId", "Signature", "Expires"}
        )

    def check_document_is_public(self, document):
        return is_s3_object_is_public(document.file.file.obj)

    def setUp(self):
        super().setUp()
        self.private_collection_restriction = CollectionViewRestrictionFactory()
        self.private_collection = self.private_collection_restriction.collection
        self.view_restriction_session_key = (
            self.private_collection_restriction.passed_view_restrictions_session_key
        )  # noqa

    def test_create_public_document(self):
        # Create document.
        document = DocumentFactory()

        # Check the document is on amazon's servers.
        self.assertTrue(self.check_s3_url(document.file.url))

        # Load the document
        url = reverse(
            "wagtaildocs_serve",
            args=(document.id, document.filename),
        )
        response = self.client.get(url)

        # Test wagtail redirects to S3.
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url)
        # Check object is public
        self.assertTrue(self.check_document_is_public(document))

    def test_create_private_document(self):
        # Create document that is part of private collection.
        document = DocumentFactory(collection=self.private_collection)

        # Check the document is on amazon's servers.
        self.assertTrue(self.check_s3_url(document.file.url))

        # Authorise the session.
        s = self.client.session
        s.update(
            {
                self.view_restriction_session_key: [
                    self.private_collection_restriction.id
                ],  # noqa
            }
        )
        s.save()

        # Load the document
        url = reverse(
            "wagtaildocs_serve",
            args=(document.id, document.filename),
        )
        response = self.client.get(url)

        # Test wagtail redirects to S3.
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url)
        # Check object is not public
        self.assertFalse(self.check_document_is_public(document))
