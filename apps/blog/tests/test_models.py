"""tests for models"""
from datetime import datetime
from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.db.utils import DataError, IntegrityError
from django_tenants.test.cases import FastTenantTestCase

from apps.blog.models import Category, Image, Post, Tag


class TagTestCase(FastTenantTestCase):
    """Tests for model `Tag`"""

    def test_creation(self):
        """Ensure we can create a `Tag` object"""
        tag = Tag.objects.create(
            name="Thesis",
            slug="thesis",
            description="All things thesis",
        )
        self.assertTrue(isinstance(tag, Tag))
        self.assertEqual(f"{tag}", "Thesis")
        self.assertEqual(tag.name, "Thesis")
        self.assertEqual(tag.slug, "thesis")
        self.assertEqual(tag.description, "All things thesis")

        # Test defaults
        tag_defaults = Tag.objects.create(name="Thesis")
        self.assertEqual(tag_defaults.description, None)

        # Test name length should not exceed 32
        with transaction.atomic(), self.assertRaises(DataError):
            # 33 chars
            Tag.objects.create(
                name="Lorem ipsum dolor sit amet, conse",
                slug="thesis",
            )

        # Test slug length should not exceed 60
        with transaction.atomic(), self.assertRaises(DataError):
            # 61 chars
            Tag.objects.create(
                name="Thesis",
                slug="lorem-ipsum-dolor-sit-amet-consectetur-adipiscing-eli-blah-bl",
            )

        # Test description should not exceed 255
        with transaction.atomic(), self.assertRaises(DataError):
            # 256 chars
            Tag.objects.create(
                name="Thesis",
                slug="thesis",
                description="""
                    Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod
                    tempor incididunt ut labore et dolore magna aliqua.
                    Ut enim ad minim veniam, quis nostrud exercitation ullamco
                    laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in
                    """,
            )


@pytest.mark.django_db
class TestCategory:
    """Tests for model `Category`"""

    def test_creation(self, use_tenant_connection):
        """Creates a Category object"""
        parent_category = Category.objects.create(
            name="Parent Category",
            slug="parent-category",
            description="I am a parent category",
        )
        category = Category.objects.create(
            name="Category",
            slug="awesome-category",
            description="Some awesome stuff",
            parent=parent_category,
        )

        assert isinstance(category, Category) is True
        assert f"{category}" == "Category"
        assert category.name == "Category"
        assert category.slug == "awesome-category"
        assert category.description == "Some awesome stuff"
        assert category.parent == parent_category
        assert parent_category.children.first() == category

    def test_defaults(self, use_tenant_connection):
        """Defaults for non-required fields"""
        category = Category.objects.create(name="Category", slug="awesome-category")

        assert category.description is None
        assert category.parent is None

    def test_name_length(self, use_tenant_connection):
        """Max length for name is 32"""
        # 33 chars fails
        invalid_name = "Lorem ipsum dolor sit amet, conse"
        assert len(invalid_name) == 33
        with transaction.atomic(), pytest.raises(DataError):
            Category.objects.create(name=invalid_name, slug="category")
        # 32 chars is created successfully
        valid_name = invalid_name[:-1]
        assert len(valid_name) == 32
        cat = Category.objects.create(name=valid_name, slug="category")
        assert cat.name == valid_name

    def test_slug_length(self, use_tenant_connection):
        """Max length for slug is 60"""
        # 61 chars fails
        invalid_slug = "lorem-ipsum-dolor-sit-amet-consectetur-adipiscing-elitsed-dop"
        assert len(invalid_slug) == 61
        with transaction.atomic(), pytest.raises(DataError):
            Category.objects.create(name="Category", slug=invalid_slug)
        # 60 chars is created successfully
        valid_slug = invalid_slug[:-1]
        assert len(valid_slug) == 60
        cat = Category.objects.create(
            name="Category",
            slug=valid_slug,
        )
        assert cat.slug == valid_slug

    def test_description_length(self, use_tenant_connection):
        """Max length for description is 160"""
        # 161 chars fails
        invalid_desc = "Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatisi"
        assert len(invalid_desc) == 161
        with transaction.atomic(), pytest.raises(DataError):
            Category.objects.create(
                name="Category", slug="category", description=invalid_desc
            )
        # 160 chars is created successfully
        valid_desc = invalid_desc[:-1]
        assert len(valid_desc) == 160
        cat = Category.objects.create(
            name="Category", slug="category", description=valid_desc
        )
        assert cat.description == valid_desc

    def test_parent_delete(self, use_tenant_connection):
        """Deleting parent category also deletes children"""
        parent_category = Category.objects.create(
            name="Parent Category",
            slug="parent-category",
            description="I am a parent category",
        )
        category = Category.objects.create(
            name="Category",
            slug="awesome-category",
            description="Some awesome stuff",
            parent=parent_category,
        )
        assert category.parent == parent_category
        parent_category.delete()
        assert Category.objects.all().count() == 0

    def test_slug_unique(self, use_tenant_connection):
        """slug should be unique"""
        Category.objects.create(
            name="Category",
            slug="awesome-category",
        )

        with transaction.atomic(), pytest.raises(IntegrityError):
            Category.objects.create(
                name="Duplicate Slug",
                slug="awesome-category",
            )


class PostTestCase(FastTenantTestCase):
    """Tests for model `Post`"""

    def setUp(self) -> None:
        super().setUp()

        # Mock storage backends to prevent a file from being saved on disk
        self.file_name = "test.doc"
        self.patcher_1 = mock.patch("django.core.files.storage.FileSystemStorage.save")
        self.mock_file_storage_save = self.patcher_1.start()
        self.mock_file_storage_save.return_value = self.file_name
        self.patcher_2 = mock.patch("storages.backends.s3boto3.S3Boto3Storage.save")
        self.mock_s3_save = self.patcher_2.start()
        self.mock_s3_save.return_value = self.file_name
        # End mock
        self.image = Image.objects.create(
            image=SimpleUploadedFile(self.file_name, b"these are the file contents!")
        )

    def tearDown(self):
        self.patcher_1.stop()
        self.patcher_2.stop()

    @mock.patch("apps.blog.utils.datetime")
    def test_creation(self, datetime_mock):
        """Ensure we can create a `Post` object"""
        tag = Tag.objects.create(name="what is")
        category = Category.objects.create(name="awesome category")
        post = Post.objects.create(
            title="What is an essay?",
            seo_title="Some awesome SEO title",
            seo_description="An essay is an essay",
            slug="what-is-an-essay",
            is_published=True,
            is_pinned=True,
            is_featured=False,
            content=[{"text": "some text"}],
            featured_image=self.image,
        )
        post.tags.add(tag)
        post.categories.add(category)
        datetime_mock.today.return_value = datetime.strptime("Jun 21 2020", "%b %d %Y")
        datetime_mock.now.return_value = datetime.strptime(
            "Jun 21 2020 09:15:32.123", "%b %d %Y %H:%M:%S.%f"
        )
        self.assertTrue(isinstance(post, Post))
        self.assertEqual(f"{post}", "What is an essay?")
        self.assertEqual(post.title, "What is an essay?")
        self.assertEqual(post.seo_title, "Some awesome SEO title")
        self.assertEqual(post.seo_description, "An essay is an essay")
        self.assertEqual(post.slug, "what-is-an-essay")
        self.assertTrue(post.is_published)
        self.assertTrue(post.is_pinned)
        self.assertFalse(post.is_featured)
        self.assertEqual(post.content, [{"text": "some text"}])
        self.assertEqual(list(post.tags.all()), list(Tag.objects.all()))
        self.assertEqual(list(post.categories.all()), list(Category.objects.all()))
        self.assertEqual(post.featured_image, self.image)

    def test_defaults(self):
        """Default values for non-require fields is ok"""
        post = Post.objects.create(
            title="What is an essay?",
            slug="slug",
        )
        self.assertIsNone(post.seo_title)
        self.assertIsNone(post.seo_description)
        self.assertEqual(post.featured_image, None)
        self.assertFalse(post.is_published)
        self.assertFalse(post.is_pinned)
        self.assertFalse(post.is_featured)
        self.assertEqual(list(post.tags.all()), list(Tag.objects.none()))
        self.assertEqual(list(post.categories.all()), list(Category.objects.none()))
        self.assertEqual(post.content, [])
        self.assertEqual(post.draft, [])

    def test_seo_title_length(self):
        """Max length for seo_title is 60"""
        # 61 chars fails
        invalid_title = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sede"
        self.assertEqual(len(invalid_title), 61)
        with transaction.atomic(), self.assertRaises(DataError):

            Post.objects.create(
                seo_title=invalid_title,
                slug="slug",
                seo_description="An essay is an essay",
            )

        # 60 chars succeeds
        valid_title = invalid_title[:-1]
        self.assertEqual(len(valid_title), 60)
        post = Post.objects.create(
            seo_title=valid_title,
            slug="slug",
            seo_description="An essay is an essay",
        )
        self.assertEqual(post.seo_title, valid_title)

    def test_seo_description_length(self):
        """Max length for seo_description is 160"""
        # 161 chars fails
        invalid_desc = "Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatisi"
        self.assertEqual(len(invalid_desc), 161)
        with transaction.atomic(), self.assertRaises(DataError):
            Post.objects.create(
                title="What is an essay?",
                slug="slug",
                seo_description=invalid_desc,
            )

        # 160 chars succeeds
        valid_desc = invalid_desc[:-1]
        self.assertEqual(len(valid_desc), 160)
        post = Post.objects.create(
            title="What is an essay?",
            slug="slug",
            seo_description=valid_desc,
        )
        self.assertEqual(post.seo_description, valid_desc)

    def test_slug_length(self):
        """Max length for slug is 60"""
        # 61 chars fails
        invalid_slug = "lorem-ipsum-dolor-sit-amet-consectetur-adipiscing-eli-blah-bl"
        self.assertEqual(len(invalid_slug), 61)
        with transaction.atomic(), self.assertRaises(DataError):
            Post.objects.create(
                title="What is an essay?",
                seo_description="An essay is an essay",
                slug=invalid_slug,
            )

        # 60 chars succeeds
        valid_slug = invalid_slug[:-1]
        self.assertEqual(len(valid_slug), 60)
        post = Post.objects.create(
            title="What is an essay?",
            seo_description="An essay is an essay",
            slug=valid_slug,
        )
        self.assertEqual(post.slug, valid_slug)

    def test_slug_unique(self):
        """No duplicates allowed for slug"""
        Post.objects.create(
            title="What is an essay?",
            seo_description="An essay is an essay",
            slug="unique-slug",
        )

        with transaction.atomic(), self.assertRaises(IntegrityError):
            Post.objects.create(
                title="Some duplicate post",
                seo_description="Some duplicate post",
                slug="unique-slug",
            )

    def test_previous_next_post(self):
        """Ensure previous and next posts returned are correct"""
        post_1 = Post.objects.create(
            title="Post 1",
            slug="post-1",
            seo_description="This is post 1",
            is_published=True,
        )
        post_2 = Post.objects.create(
            title="Post 2",
            slug="post-2",
            seo_description="This is post 2",
            is_published=False,
        )
        post_3 = Post.objects.create(
            title="Post 3",
            slug="post-3",
            seo_description="This is post 3",
            is_published=True,
        )
        self.assertEqual(post_1.previous_post, None)
        # Since post 2 is unpublished, next post should be the next published
        self.assertEqual(post_1.next_post, post_3)

        self.assertEqual(post_2.previous_post, post_1)
        self.assertEqual(post_2.next_post, post_3)
        # Since post 2 is unpublished, next post should be the previous published
        self.assertEqual(post_3.previous_post, post_1)
        self.assertEqual(post_3.next_post, None)

    def test_publish(self):
        """Publishes a post"""
        post = Post.objects.create(
            title="Post 1",
            slug="post-1",
            seo_description="This is post 1",
            is_published=False,
            content=[{"text": "some old content"}],
            draft=[{"text": "draft content"}],
        )
        post.publish()
        post.refresh_from_db()
        self.assertEqual(post.content, [{"text": "draft content"}])
        self.assertTrue(post.is_published)
