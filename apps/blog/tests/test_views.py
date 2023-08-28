"""Tests for blog views"""

import json
from unittest import mock

import dateutil
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.serializers.json import DjangoJSONEncoder
from django.http import SimpleCookie
from django.urls import reverse
from django_tenants.test.cases import FastTenantTestCase
from django_tenants.test.client import TenantClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.blog.models import Category
from apps.blog.models import Image as BlogImage
from apps.blog.models import Post, Tag
from apps.common.utils import reverse_querystring
from apps.subscription.models import Subscription


class GetAllPostsTestCase(FastTenantTestCase):
    """Tests for GET all posts"""

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
        # create active subscription
        Subscription.objects.create(
            is_on_trial=False,
            status=Subscription.Status.ACTIVE,
            start_time=dateutil.parser.parse(
                "2016-01-01T00:20:49Z",
            ),
            next_billing_time=dateutil.parser.parse(
                "2016-05-01T00:20:49Z",
            ),
        )

    @mock.patch("storages.backends.s3boto3.S3Boto3Storage.save")
    @mock.patch("django.core.files.storage.FileSystemStorage.save")
    def test_get_all_posts(
        self,
        mock_system_storage,
        mock_s3_storage,
    ):
        """Ensure get all posts is correct"""
        file_name = "file.jpg"
        mock_system_storage.return_value = file_name
        mock_s3_storage.return_value = file_name
        file = SimpleUploadedFile("file.jpg", b"these are the file contents!")
        blog_image = BlogImage.objects.create(image=file)

        Post.objects.create(
            title="Post 1",
            seo_title="SEO title",
            seo_description="Some description",
            slug="post-1",
            is_published=True,
            is_pinned=True,
            is_featured=False,
            content="Some good content",
            featured_image=blog_image,
        )
        Post.objects.create(
            title="Post 2",
            seo_title="SEO title",
            seo_description="Some description for post 2",
            slug="post-2",
            is_published=True,
            is_pinned=True,
            is_featured=False,
            content="Some good content for post 2",
        )
        response = self.client.get(reverse("post-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["results"],
            [
                {
                    "title": "Post 2",
                    "slug": "post-2",
                    "seo_title": "SEO title",
                    "seo_description": "Some description for post 2",
                    "featured_image": None,
                    "is_published": True,
                },
                {
                    "title": "Post 1",
                    "slug": "post-1",
                    "seo_title": "SEO title",
                    "seo_description": "Some description",
                    "featured_image": {
                        "id": str(blog_image.id),
                        "image": blog_image.image.url,
                    },
                    "is_published": True,
                },
            ],
        )

    def test_filters_work(self):
        """Query parameter filters work"""
        tag_1 = Tag.objects.create(name="Tag 1", slug="tag-1")
        category_1 = Category.objects.create(name="Category 1", slug="category-1")
        post_1 = Post.objects.create(
            title="Post 1",
            seo_title="SEO title",
            seo_description="Some description",
            slug="post-1",
            is_published=False,
            is_pinned=True,
            is_featured=True,
            content="Some good content",
        )
        post_1.tags.add(tag_1)
        post_2 = Post.objects.create(
            title="Post 2",
            seo_title="SEO title",
            seo_description="Some description for post 2",
            slug="post-2",
            is_published=True,
            is_pinned=False,
            is_featured=False,
            content="Some good content for post 2",
        )
        post_2.categories.add(category_1)
        # filter by title
        response = self.client.get(
            reverse_querystring(
                "post-list",
                query_kwargs={"title": "Post 2"},
            )
        )
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["slug"], "post-2")
        # filter by tag slug
        response = self.client.get(
            reverse_querystring(
                "post-list",
                query_kwargs={"tag_slug": "tag-1"},
            )
        )
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["slug"], "post-1")
        # filter by category slug
        response = self.client.get(
            reverse_querystring(
                "post-list",
                query_kwargs={"category_slug": "category-1"},
            )
        )
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["slug"], "post-2")
        # filter by is_published
        response = self.client.get(
            reverse_querystring(
                "post-list",
                query_kwargs={"is_published": True},
            )
        )
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["slug"], "post-2")
        # filter by is_pinned
        response = self.client.get(
            reverse_querystring(
                "post-list",
                query_kwargs={"is_pinned": True},
            )
        )
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["slug"], "post-1")
        # filter by is_featured
        response = self.client.get(
            reverse_querystring(
                "post-list",
                query_kwargs={"is_featured": True},
            )
        )
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["slug"], "post-1")


@pytest.mark.django_db
class TestCreatePost:
    """Tests for create post"""

    def test_subscription_active(self, use_tenant_connection, fast_tenant_client):
        """Tenant subscription should be active"""
        response = fast_tenant_client.post(reverse("post-list"), data={})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_authentication(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        response = fast_tenant_client.post(reverse("post-list"), data={})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_only_staff_allowed(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        customer,
    ):
        """Only staff can create post"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.post(reverse("post-list"), data={})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @mock.patch("storages.backends.s3boto3.S3Boto3Storage.save")
    @mock.patch("django.core.files.storage.FileSystemStorage.save")
    def test_create(
        self,
        mock_system_storage,
        mock_s3_storage,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """Post is created"""
        # Mock storage backends to prevent a file from being saved on disk
        file_name = "file.jpg"
        mock_system_storage.return_value = file_name
        mock_s3_storage.return_value = file_name
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        cat_1 = Category.objects.create(name="Category 1", slug="category-1")
        cat_2 = Category.objects.create(name="Category 2", slug="category-2")
        tag_1 = Tag.objects.create(name="Tag 1", slug="tag-1")
        tag_2 = Tag.objects.create(name="Tag 2", slug="tag-2")
        file = SimpleUploadedFile("file.jpg", b"these are the file contents!")
        blog_image = BlogImage.objects.create(image=file)
        response = fast_tenant_client.post(
            reverse("post-list"),
            data={
                "title": "Awesome post",
                "seo_title": "SEO title",
                "seo_description": "This is just a post",
                "slug": "this-just-post",
                "featured_image": str(blog_image.id),
                "is_published": True,
                "is_featured": True,
                "is_pinned": True,
                "categories": [str(cat_1.id), str(cat_2.id)],
                "tags": [str(tag_1.id), str(tag_2.id)],
                "draft": json.dumps([{"text": "some text"}], cls=DjangoJSONEncoder),
                "publish": True,
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert len(Post.objects.all()) == 1
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            {
                "title": "Awesome post",
                "slug": "this-just-post",
                "seo_title": "SEO title",
                "seo_description": "This is just a post",
                "featured_image": str(blog_image.id),
                "is_published": True,
                "is_featured": True,
                "is_pinned": True,
                "categories": [str(cat_1.id), str(cat_2.id)],
                "tags": [str(tag_2.id), str(tag_1.id)],
                "content": [{"text": "some text"}],
                "draft": [{"text": "some text"}],
            },
            cls=DjangoJSONEncoder,
        )

    def test_title_required(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """title is required"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        # empty title fails
        response = fast_tenant_client.post(
            reverse("post-list"),
            data={
                "title": "",
                "slug": "this-just-post",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # title missing fails
        response = fast_tenant_client.post(
            reverse("post-list"),
            data={
                "slug": "this-just-post",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_seo_title_length(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """seo_title should not be more than 60 chars"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        # 61 chars fails
        invalid_title = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sede"
        assert len(invalid_title) == 61
        response = fast_tenant_client.post(
            reverse("post-list"),
            data={
                "title": "Just a title",
                "seo_title": invalid_title,
                "slug": "this-just-post",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # 60 chars succeeds
        valid_title = invalid_title[:-1]
        assert len(valid_title) == 60
        response = fast_tenant_client.post(
            reverse("post-list"),
            data={
                "title": "Just a title",
                "seo_title": valid_title,
                "slug": "this-just-post",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_slug_required(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """slug is required"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        # empty slug fails
        response = fast_tenant_client.post(
            reverse("post-list"),
            data={
                "title": "Post",
                "slug": "",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # missing slug fails
        response = fast_tenant_client.post(
            reverse("post-list"),
            data={
                "title": "Post",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_slug_length(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """Max length for slug is 60 chars"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        # 61 chars fails
        invalid_slug = "lorem-ipsum-dolor-sit-amet-consectetur-adipiscing-eli-blah-bl"
        assert len(invalid_slug) == 61
        response = fast_tenant_client.post(
            reverse("post-list"),
            data={
                "title": "Post",
                "slug": invalid_slug,
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # 60 chars succeeds
        valid_slug = invalid_slug[:-1]
        assert len(valid_slug) == 60
        response = fast_tenant_client.post(
            reverse("post-list"),
            data={
                "title": "Post",
                "slug": valid_slug,
            },
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_slug_unique(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """A post with slug posted should not exist"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        Post.objects.create(title="Post", slug="nice-post")

        response = fast_tenant_client.post(
            reverse("post-list"),
            data={
                "title": "Post",
                "slug": "nice-post",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_seo_description_length(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """Max length for descrition is 160 chars"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        # 161 chars fails
        invalid_desc = "Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatisi"
        response = fast_tenant_client.post(
            reverse("post-list"),
            data={
                "title": "Post",
                "slug": "post",
                "seo_description": invalid_desc,
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # 160 chars succeeds
        valid_desc = invalid_desc[:-1]
        response = fast_tenant_client.post(
            reverse("post-list"),
            data={
                "title": "Post",
                "slug": "post",
                "seo_description": valid_desc,
            },
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_content_is_read_only(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """content field is read only"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.post(
            reverse("post-list"),
            data={
                "title": "Post",
                "slug": "post",
                "content": [{"text": "text here"}],
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        post = Post.objects.get(slug="post")
        assert post.content == []

    def test_publish_works(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """pubish works correctly"""
        # should not publish content if publish is False
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.post(
            reverse("post-list"),
            data={
                "title": "Post",
                "slug": "published-false",
                "draft": json.dumps([{"text": "text here"}], cls=DjangoJSONEncoder),
                "publish": False,
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        post = Post.objects.get(slug="published-false")
        assert post.content == []

        # should publish content if publish is True
        response = fast_tenant_client.post(
            reverse("post-list"),
            data={
                "title": "Post",
                "slug": "published-true",
                "draft": json.dumps([{"text": "text here"}], cls=DjangoJSONEncoder),
                "publish": True,
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        post = Post.objects.get(slug="published-true")
        assert post.content == [{"text": "text here"}]


@pytest.mark.django_db
class TestUpdatePost:
    """Tests for update post"""

    @pytest.fixture()
    def set_up(self):
        cat_1 = Category.objects.create(name="Category 1", slug="category-1")
        cat_2 = Category.objects.create(name="Category 2", slug="category-2")
        cat_3 = Category.objects.create(name="Category 3", slug="category-3")
        tag_1 = Tag.objects.create(name="Tag 1", slug="tag-1")
        tag_2 = Tag.objects.create(name="Tag 2", slug="tag-2")
        tag_3 = Tag.objects.create(name="Tag 3", slug="tag-3")
        post = Post.objects.create(
            title="Post",
            slug="nice-post",
            seo_title="SEO Post",
            seo_description="Awesome post",
            is_published=False,
            is_pinned=False,
            is_featured=False,
            content=[{"text": "old content"}],
            draft=[{"text": "old draft"}],
        )
        post.categories.add(cat_1)
        post.tags.add(tag_1)

        return locals()

    def test_subscription_active(
        self,
        use_tenant_connection,
        fast_tenant_client,
    ):
        """Tenant subscription should be active"""
        response = fast_tenant_client.put(
            reverse("post-detail", kwargs={"slug": "nice-post"}), data={}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_authentication(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
    ):
        """Authentication is required"""
        response = fast_tenant_client.put(
            reverse("post-detail", kwargs={"slug": "nice-post"}), data={}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_only_staff_allowed(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        customer,
    ):
        """Only staff can create post"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.put(
            reverse("post-detail", kwargs={"slug": "nice-post"}), data={}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @mock.patch("storages.backends.s3boto3.S3Boto3Storage.save")
    @mock.patch("django.core.files.storage.FileSystemStorage.save")
    def test_update_post(
        self,
        mock_system_storage,
        mock_s3_storage,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
        set_up,
    ):
        """Updates a singe post"""
        mock_system_storage.return_value = "file.jpg"
        mock_s3_storage.return_value = "file.jpg"
        cat_2 = set_up["cat_2"]
        cat_3 = set_up["cat_3"]
        tag_2 = set_up["tag_2"]
        tag_3 = set_up["tag_3"]
        post = set_up["post"]
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        file = SimpleUploadedFile("file.jpg", b"these are the file contents!")
        blog_image = BlogImage.objects.create(image=file)
        response = fast_tenant_client.put(
            reverse("post-detail", kwargs={"slug": post.slug}),
            data=json.dumps(
                {
                    "title": "Updated title",
                    "slug": "updated-slug",
                    "seo_title": "Updated SEO title",
                    "seo_description": "Updated description",
                    "featured_image": str(blog_image.id),
                    "is_published": True,
                    "is_featured": True,
                    "is_pinned": True,
                    "categories": [str(cat_2.id), str(cat_3.id)],
                    "tags": [str(tag_2.id), str(tag_3.id)],
                    "draft": [{"text": "updated draft"}],
                    "publish": True,
                },
                cls=DjangoJSONEncoder,
            ),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        post.refresh_from_db()
        assert post.title == "Updated title"
        assert post.slug == "updated-slug"
        assert post.seo_description == "Updated description"
        assert post.featured_image is not None
        assert post.is_published is True
        assert post.is_featured is True
        assert post.is_pinned is True
        assert list(post.categories.all()) == [cat_2, cat_3]
        assert list(post.tags.all()) == [tag_3, tag_2]
        assert post.draft == [{"text": "updated draft"}]
        assert post.content == [{"text": "updated draft"}]
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            {
                "title": "Updated title",
                "slug": "updated-slug",
                "seo_title": "Updated SEO title",
                "seo_description": "Updated description",
                "featured_image": str(blog_image.id),
                "is_published": True,
                "is_featured": True,
                "is_pinned": True,
                "categories": [str(cat_2.id), str(cat_3.id)],
                "tags": [str(tag_3.id), str(tag_2.id)],
                "content": [{"text": "updated draft"}],
                "draft": [{"text": "updated draft"}],
            },
            cls=DjangoJSONEncoder,
        )

    def test_invalid_post(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """Invalid post is handled correctly"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.put(
            reverse("post-detail", kwargs={"slug": "does-not-exist"}),
            data={},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestDeletePost:
    """Test for delete single post"""

    def test_subscription_active(
        self,
        use_tenant_connection,
        fast_tenant_client,
    ):
        """Tenant subscription should be active"""
        response = fast_tenant_client.delete(
            reverse("post-detail", kwargs={"slug": "nice-post"})
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_authentication(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
    ):
        """Authentication is required"""
        response = fast_tenant_client.delete(
            reverse("post-detail", kwargs={"slug": "nice-post"})
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_only_staff_allowed(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        customer,
    ):
        """Only staff can delete post"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.delete(
            reverse("post-detail", kwargs={"slug": "nice-post"})
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_post_deleted(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """Post is deleted"""
        post = Post.objects.create(
            title="Post",
            slug="to-be-deleted",
        )
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.delete(
            reverse("post-detail", kwargs={"slug": post.slug})
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Post.objects.all().count() == 0

    def test_invalid_post(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """Invalid post is handled correctly"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.delete(
            reverse("post-detail", kwargs={"slug": "does-not-exist"})
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class GetSinglePostTestCase(FastTenantTestCase):
    """Tests for GET single post"""

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
        # create active subscription
        Subscription.objects.create(
            is_on_trial=False,
            status=Subscription.Status.ACTIVE,
            start_time=dateutil.parser.parse(
                "2016-01-01T00:20:49Z",
            ),
            next_billing_time=dateutil.parser.parse(
                "2016-05-01T00:20:49Z",
            ),
        )

    @mock.patch("storages.backends.s3boto3.S3Boto3Storage.save")
    @mock.patch("django.core.files.storage.FileSystemStorage.save")
    def test_get_single(
        self,
        mock_system_storage,
        mock_s3_storage,
    ):
        """Ensure GET single post works correctly"""
        file_name = "file.jpg"
        mock_system_storage.return_value = file_name
        mock_s3_storage.return_value = file_name
        file = SimpleUploadedFile("file.jpg", b"these are the file contents!")
        blog_image = BlogImage.objects.create(image=file)

        Post.objects.create(
            title="Post 1",
            seo_title="SEO Post 1",
            seo_description="Some description",
            slug="post-1",
            is_published=True,
            is_pinned=False,
            is_featured=False,
            content=[{"text": "some text"}],
            draft=[{"text": "some text"}],
            featured_image=blog_image,
        )
        post_2 = Post.objects.create(
            title="Post 2",
            seo_title="SEO Post 2",
            seo_description="Some description for post 2",
            slug="post-2",
            is_published=True,
            is_pinned=False,
            is_featured=False,
            content=[{"text": "some text"}],
            draft=[{"text": "some text"}],
        )
        post_3 = Post.objects.create(
            title="Post 3",
            seo_title="SEO Post 3",
            seo_description="Some description for post 3",
            slug="post-3",
            is_published=True,
            is_pinned=False,
            is_featured=False,
            content=[{"text": "some text"}],
            draft=[{"text": "some text"}],
        )
        tag = Tag.objects.create(name="tag", slug="awesome-tag")
        post_2.tags.add(tag)
        category = Category.objects.create(name="Category", slug="awesome-category")
        post_3.categories.add(category)

        # Test post 1 response
        response = self.client.get(reverse("post-detail", kwargs={"slug": "post-1"}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {
                "title": "Post 1",
                "slug": "post-1",
                "seo_title": "SEO Post 1",
                "seo_description": "Some description",
                "featured_image": {
                    "id": str(blog_image.id),
                    "image": blog_image.image.url,
                },
                "is_published": True,
                "is_featured": False,
                "is_pinned": False,
                "tags": [],
                "categories": [],
                "content": [{"text": "some text"}],
                "draft": [{"text": "some text"}],
                "previous_post": None,
                "next_post": {"title": "Post 2", "slug": "post-2"},
            },
        )

        # Test post 2 response
        response = self.client.get(reverse("post-detail", kwargs={"slug": "post-2"}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {
                "title": "Post 2",
                "slug": "post-2",
                "seo_title": "SEO Post 2",
                "seo_description": "Some description for post 2",
                "featured_image": None,
                "is_published": True,
                "is_featured": False,
                "is_pinned": False,
                "tags": [{"id": str(tag.id), "name": tag.name, "slug": tag.slug}],
                "categories": [],
                "content": [{"text": "some text"}],
                "draft": [{"text": "some text"}],
                "previous_post": {"title": "Post 1", "slug": "post-1"},
                "next_post": {"title": "Post 3", "slug": "post-3"},
            },
        )

        # Test post 3 response
        response = self.client.get(reverse("post-detail", kwargs={"slug": post_3.slug}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {
                "title": "Post 3",
                "slug": "post-3",
                "seo_title": "SEO Post 3",
                "seo_description": "Some description for post 3",
                "featured_image": None,
                "is_published": True,
                "is_featured": False,
                "is_pinned": False,
                "tags": [],
                "categories": [
                    {
                        "id": str(category.id),
                        "name": category.name,
                        "slug": category.slug,
                    }
                ],
                "content": [{"text": "some text"}],
                "draft": [{"text": "some text"}],
                "previous_post": {"title": "Post 2", "slug": "post-2"},
                "next_post": None,
            },
        )


class GetAllTagsTestCase(FastTenantTestCase):
    """Tests for GET all tags"""

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
        # create active subscription
        Subscription.objects.create(
            is_on_trial=False,
            status=Subscription.Status.ACTIVE,
            start_time=dateutil.parser.parse(
                "2016-01-01T00:20:49Z",
            ),
            next_billing_time=dateutil.parser.parse(
                "2016-05-01T00:20:49Z",
            ),
        )

    def test_get_all(self):
        """Ensure get all is correct"""
        tag_1 = Tag.objects.create(
            name="Tag 1", slug="tag-1", description="All things tag 1"
        )
        tag_2 = Tag.objects.create(name="Tag 2", slug="tag-2")

        response = self.client.get(reverse("tag-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            [
                {
                    "id": str(tag_2.id),
                    "name": tag_2.name,
                    "slug": tag_2.slug,
                },
                {
                    "id": str(tag_1.id),
                    "name": tag_1.name,
                    "slug": tag_1.slug,
                },
            ],
        )

    def test_filters(self):
        """Query parameter filters work"""
        Tag.objects.create(name="Tag 1", slug="tag-1", description="All things tag 1")
        Tag.objects.create(name="Tag 2", slug="tag-2")
        # filter by name
        response = self.client.get(
            reverse_querystring(
                "tag-list",
                query_kwargs={"name": "Tag 2"},
            )
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["slug"], "tag-2")


@pytest.mark.django_db
class TestCreateTag:
    """Tests for create single tag"""

    def test_subscription_active(self, use_tenant_connection, fast_tenant_client):
        """Tenant subscription should be active"""
        response = fast_tenant_client.post(reverse("tag-list"), data={})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_authentication(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        response = fast_tenant_client.post(reverse("tag-list"), data={})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_only_staff_allowed(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        customer,
    ):
        """Only staff can create post"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.post(reverse("tag-list"), data={})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_tag(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """Tag is created successfully"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.post(
            reverse("tag-list"),
            data={
                "name": "Business",
                "slug": "business",
                "description": "All about business",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Tag.objects.all().count() == 1
        tag = Tag.objects.first()
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            {
                "id": str(tag.id),
                "name": "Business",
                "slug": "business",
                "description": "All about business",
            },
            cls=DjangoJSONEncoder,
        )

    def test_name_required(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """name field is required"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.post(
            reverse("tag-list"),
            data={
                "name": "",
                "slug": "business",
                "description": "All about business",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Tag.objects.all().count() == 0

    def test_name_length(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """Max length for name is 32 chars"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        # 33 chars fails
        invalid_name = "Sed ut perspiciatis unde omnispil"
        assert len(invalid_name) == 33
        response = fast_tenant_client.post(
            reverse("tag-list"),
            data={
                "name": invalid_name,
                "slug": "business",
                "description": "All about business",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Tag.objects.all().count() == 0

        # 32 chars succeeds
        valid_name = invalid_name[:-1]
        assert len(valid_name) == 32
        response = fast_tenant_client.post(
            reverse("tag-list"),
            data={
                "name": valid_name,
                "slug": "business",
                "description": "All about business",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Tag.objects.all().count() == 1

    def test_slug_required(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """slug field is required"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.post(
            reverse("tag-list"),
            data={
                "name": "Business",
                "slug": "",
                "description": "All about business",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Tag.objects.all().count() == 0

    def test_slug_length(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """Max length for slug is 60 chars"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        # 61 chars fails
        invalid_slug = "lorem-ipsum-dolor-sit-amet-consectetur-adipiscing-elitsed-dop"
        assert len(invalid_slug) == 61
        response = fast_tenant_client.post(
            reverse("tag-list"),
            data={
                "name": "Business",
                "slug": invalid_slug,
                "description": "All about business",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Tag.objects.all().count() == 0

        # 60 chars succeeds
        valid_slug = invalid_slug[:-1]
        assert len(valid_slug) == 60
        response = fast_tenant_client.post(
            reverse("tag-list"),
            data={
                "name": "Business",
                "slug": valid_slug,
                "description": "All about business",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Tag.objects.all().count() == 1

    def test_description_length(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """Max length for description is 160 chars"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        # 161 chars fails
        invalid_desc = "Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatisi"
        assert len(invalid_desc) == 161
        response = fast_tenant_client.post(
            reverse("tag-list"),
            data={
                "name": "Business",
                "slug": "business",
                "description": invalid_desc,
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Tag.objects.all().count() == 0

        # 160 chars succeeds
        valid_desc = invalid_desc[:-1]
        assert len(valid_desc) == 160
        response = fast_tenant_client.post(
            reverse("tag-list"),
            data={
                "name": "Business",
                "slug": "business",
                "description": valid_desc,
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Tag.objects.all().count() == 1


@pytest.mark.django_db
class TestUpdateTag:
    """Tests for updating a tag"""

    @pytest.fixture()
    def set_up(self):
        tag = Tag.objects.create(
            name="Tag 1",
            slug="slug-1",
            description="Nice tag",
        )

        return locals()

    def test_subscription_active(
        self,
        use_tenant_connection,
        fast_tenant_client,
        dummy_uuid,
    ):
        """Tenant subscription should be active"""
        response = fast_tenant_client.put(
            reverse(
                "tag-detail",
                kwargs={
                    "pk": dummy_uuid,
                },
            ),
            data={},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_authentication(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        dummy_uuid,
    ):
        """Authentication is required"""
        response = fast_tenant_client.put(
            reverse(
                "tag-detail",
                kwargs={"pk": dummy_uuid},
            ),
            data={},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_only_staff_allowed(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        customer,
        dummy_uuid,
    ):
        """Only staff can create post"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.put(
            reverse(
                "tag-detail",
                kwargs={"pk": dummy_uuid},
            ),
            data={},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_tag(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
        set_up,
    ):
        """tag is updated"""
        tag = set_up["tag"]
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.put(
            reverse(
                "tag-detail",
                kwargs={"pk": tag.id},
            ),
            data=json.dumps(
                {
                    "name": "Updated tag",
                    "slug": "updated-slug",
                    "description": "Updated description",
                },
                cls=DjangoJSONEncoder,
            ),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            {
                "id": str(tag.id),
                "name": "Updated tag",
                "slug": "updated-slug",
                "description": "Updated description",
            },
            cls=DjangoJSONEncoder,
        )
        tag.refresh_from_db()
        assert tag.name == "Updated tag"
        assert tag.slug == "updated-slug"
        assert tag.description == "Updated description"

    def test_invalid_tag(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
        dummy_uuid,
    ):
        """Invalid post is handled correctly"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.put(
            reverse(
                "tag-detail",
                kwargs={"pk": dummy_uuid},
            ),
            data={},
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_name_required(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
        set_up,
    ):
        """name field is required"""
        tag = set_up["tag"]
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.patch(
            reverse(
                "tag-detail",
                kwargs={"pk": tag.id},
            ),
            data={"name": ""},
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_slug_required(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
        set_up,
    ):
        """slug field is required"""
        tag = set_up["tag"]
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.patch(
            reverse(
                "tag-detail",
                kwargs={"pk": tag.id},
            ),
            data={"slug": ""},
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestDeleteTag:
    """Tests for deleting a tag"""

    def test_subscription_active(
        self,
        use_tenant_connection,
        fast_tenant_client,
        dummy_uuid,
    ):
        """Tenant subscription should be active"""
        response = fast_tenant_client.delete(
            reverse(
                "tag-detail",
                kwargs={
                    "pk": dummy_uuid,
                },
            )
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_authentication(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        dummy_uuid,
    ):
        """Authentication is required"""
        response = fast_tenant_client.delete(
            reverse(
                "tag-detail",
                kwargs={"pk": dummy_uuid},
            )
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_only_staff_allowed(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        customer,
        dummy_uuid,
    ):
        """Only staff can create post"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.delete(
            reverse(
                "tag-detail",
                kwargs={"pk": dummy_uuid},
            )
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_tag(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """Tag is deleted"""
        tag = Tag.objects.create(name="Tag", slug="tag")
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.delete(
            reverse(
                "tag-detail",
                kwargs={"pk": tag.id},
            )
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Tag.objects.all().count() == 0

    def test_invalid_tag(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
        dummy_uuid,
    ):
        """Invalid tag is handled"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.delete(
            reverse(
                "tag-detail",
                kwargs={"pk": dummy_uuid},
            )
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestCreateCategory:
    """Tests for creating single category"""

    def test_subscription_active(
        self,
        use_tenant_connection,
        fast_tenant_client,
    ):
        """Tenant subscription should be active"""
        response = fast_tenant_client.post(reverse("category-list"), data={})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_authentication(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
    ):
        """Authentication is required"""
        response = fast_tenant_client.post(reverse("category-list"), data={})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_only_staff_allowed(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        customer,
    ):
        """Only staff can create post"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.post(reverse("category-list"), data={})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_category(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """Category is created"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        parent = Category.objects.create(name="Parent category", slug="parent-cat")
        response = fast_tenant_client.post(
            reverse("category-list"),
            data={
                "name": "Create category",
                "slug": "create-category",
                "description": "Created from endpoint",
                "parent": str(parent.id),
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        cat = Category.objects.get(slug="create-category")
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            {
                "id": str(cat.id),
                "name": "Create category",
                "slug": "create-category",
                "parent": str(parent.id),
                "description": "Created from endpoint",
            },
            cls=DjangoJSONEncoder,
        )

    def test_name_required(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """name field is required"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        parent = Category.objects.create(name="Parent category", slug="parent-cat")
        response = fast_tenant_client.post(
            reverse("category-list"),
            data={
                "name": "",
                "slug": "create-category",
                "description": "Created from endpoint",
                "parent": str(parent.id),
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_slug_required(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """name field is required"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        parent = Category.objects.create(name="Parent category", slug="parent-cat")
        response = fast_tenant_client.post(
            reverse("category-list"),
            data={
                "name": "Create category",
                "slug": "",
                "description": "Created from endpoint",
                "parent": str(parent.id),
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_optional_fields(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """Optional fields if not provided, category is still created"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.post(
            reverse("category-list"),
            data={
                "name": "Create category",
                "slug": "create-cat",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        cat = Category.objects.get(slug="create-cat")
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            {
                "id": str(cat.id),
                "name": "Create category",
                "slug": "create-cat",
                "parent": None,
                "description": None,
            },
            cls=DjangoJSONEncoder,
        )

    def test_name_length(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """Max length for name is 32"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        # 33 chars fails
        invalid_name = "Sed ut perspiciatis unde omnispil"
        assert len(invalid_name) == 33
        response = fast_tenant_client.post(
            reverse("category-list"),
            data={
                "name": invalid_name,
                "slug": "business",
                "description": "All about business",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Category.objects.all().count() == 0

        # 32 chars succeeds
        valid_name = invalid_name[:-1]
        assert len(valid_name) == 32
        response = fast_tenant_client.post(
            reverse("category-list"),
            data={
                "name": valid_name,
                "slug": "business",
                "description": "All about business",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Category.objects.all().count() == 1

    def test_slug_length(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """Max length for slug is 60 chars"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        # 61 chars fails
        invalid_slug = "lorem-ipsum-dolor-sit-amet-consectetur-adipiscing-elitsed-dop"
        assert len(invalid_slug) == 61
        response = fast_tenant_client.post(
            reverse("category-list"),
            data={
                "name": "Business",
                "slug": invalid_slug,
                "description": "All about business",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Category.objects.all().count() == 0

        # 60 chars succeeds
        valid_slug = invalid_slug[:-1]
        assert len(valid_slug) == 60
        response = fast_tenant_client.post(
            reverse("category-list"),
            data={
                "name": "Business",
                "slug": valid_slug,
                "description": "All about business",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Category.objects.all().count() == 1

    def test_description_length(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """Max length for description is 160 chars"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        # 161 chars fails
        invalid_desc = "Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatisi"
        assert len(invalid_desc) == 161
        response = fast_tenant_client.post(
            reverse("category-list"),
            data={
                "name": "Business",
                "slug": "business",
                "description": invalid_desc,
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Category.objects.all().count() == 0

        # 160 chars succeeds
        valid_desc = invalid_desc[:-1]
        assert len(valid_desc) == 160
        response = fast_tenant_client.post(
            reverse("category-list"),
            data={
                "name": "Business",
                "slug": "business",
                "description": valid_desc,
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Category.objects.all().count() == 1


@pytest.mark.django_db
class TestUpdateCategory:
    """Tests for update single category"""

    @pytest.fixture()
    def set_up(self):
        parent_1 = Category.objects.create(name="Parent 1", slug="parent-cat-1")
        parent_2 = Category.objects.create(name="Parent 2", slug="parent-cat-2")
        cat = Category.objects.create(
            name="Category",
            slug="category",
            parent=parent_1,
            description="A nice category",
        )

        return locals()

    def test_subscription_active(
        self,
        use_tenant_connection,
        fast_tenant_client,
        dummy_uuid,
    ):
        """Tenant subscription should be active"""
        response = fast_tenant_client.put(
            reverse(
                "category-detail",
                kwargs={"pk": dummy_uuid},
            ),
            data={},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_authentication(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        dummy_uuid,
    ):
        """Authentication is required"""
        response = fast_tenant_client.put(
            reverse(
                "category-detail",
                kwargs={"pk": dummy_uuid},
            ),
            data={},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_only_staff_allowed(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        customer,
        dummy_uuid,
    ):
        """Only staff can create post"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.put(
            reverse(
                "category-detail",
                kwargs={"pk": dummy_uuid},
            ),
            data={},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_category(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
        set_up,
    ):
        """Category is updated"""
        cat = set_up["cat"]
        parent_2 = set_up["parent_2"]
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.put(
            reverse(
                "category-detail",
                kwargs={"pk": cat.id},
            ),
            data=json.dumps(
                {
                    "name": "Updated name",
                    "slug": "updated-name",
                    "parent": str(parent_2.id),
                    "description": "Updated description",
                },
                cls=DjangoJSONEncoder,
            ),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            {
                "id": str(cat.id),
                "name": "Updated name",
                "slug": "updated-name",
                "parent": str(parent_2.id),
                "description": "Updated description",
            },
            cls=DjangoJSONEncoder,
        )
        cat.refresh_from_db()
        assert cat.name == "Updated name"
        assert cat.slug == "updated-name"
        assert cat.parent == parent_2
        assert cat.description == "Updated description"

    def test_invalid_category(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
        dummy_uuid,
    ):
        """Invalid category is handled"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.put(
            reverse(
                "category-detail",
                kwargs={"pk": dummy_uuid},
            ),
            data={},
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_parent_meets_constraints(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
        set_up,
    ):
        """Parent category constraints are met"""
        cat = set_up["cat"]
        parent_1 = set_up["parent_1"]
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        # parent cannot be self
        response = fast_tenant_client.patch(
            reverse(
                "category-detail",
                kwargs={"pk": cat.id},
            ),
            data=json.dumps({"parent": str(cat.id)}, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # parent cannot be a descendant
        response = fast_tenant_client.patch(
            reverse(
                "category-detail",
                kwargs={"pk": parent_1.id},
            ),
            data=json.dumps({"parent": str(cat.id)}, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestDeleteCategory:
    """Tests for deleting single category"""

    def test_subscription_active(
        self,
        use_tenant_connection,
        fast_tenant_client,
        dummy_uuid,
    ):
        """Tenant subscription should be active"""
        response = fast_tenant_client.delete(
            reverse(
                "category-detail",
                kwargs={"pk": dummy_uuid},
            ),
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_authentication(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        dummy_uuid,
    ):
        """Authentication is required"""
        response = fast_tenant_client.delete(
            reverse(
                "category-detail",
                kwargs={"pk": dummy_uuid},
            ),
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_only_staff_allowed(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        customer,
        dummy_uuid,
    ):
        """Only staff can create post"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.delete(
            reverse(
                "category-detail",
                kwargs={"pk": dummy_uuid},
            ),
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_category(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
    ):
        """Category is deleted"""
        cat = Category.objects.create(name="Category", slug="cat")
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.delete(
            reverse(
                "category-detail",
                kwargs={"pk": cat.id},
            ),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Category.objects.all().count() == 0

    def test_invalid_category(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        store_staff,
        dummy_uuid,
    ):
        """Invalid category is handled"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.delete(
            reverse(
                "category-detail",
                kwargs={"pk": dummy_uuid},
            ),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestGetAllCategories:
    """Tests for get all categories"""

    @pytest.fixture()
    def set_up(self):
        cat_1 = Category.objects.create(
            name="Category 1",
            slug="cat-1",
            description="I am category 1",
        )
        cat_2 = Category.objects.create(
            name="Category 2",
            slug="cat-2",
            parent=cat_1,
        )
        cat_3 = Category.objects.create(
            name="Category 3",
            slug="cat-3",
        )

        return locals()

    def test_subscription_active(
        self,
        use_tenant_connection,
        fast_tenant_client,
    ):
        """Tenant subscription should be active"""
        response = fast_tenant_client.get(
            reverse("category-list"),
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_all_categories(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        set_up,
    ):
        """All categories are returned"""
        cat_1 = set_up["cat_1"]
        cat_2 = set_up["cat_2"]
        cat_3 = set_up["cat_3"]
        response = fast_tenant_client.get(
            reverse("category-list"),
        )
        assert response.status_code == status.HTTP_200_OK
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            [
                {
                    "id": str(cat_1.id),
                    "name": "Category 1",
                    "slug": "cat-1",
                    "children": [
                        {
                            "id": str(cat_2.id),
                            "name": "Category 2",
                            "slug": "cat-2",
                            "children": [],
                        },
                    ],
                },
                {
                    "id": str(cat_3.id),
                    "name": "Category 3",
                    "slug": "cat-3",
                    "children": [],
                },
            ],
            cls=DjangoJSONEncoder,
        )

    def test_filters(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
        set_up,
    ):
        """Query param filters work"""
        # filter by name works
        response = fast_tenant_client.get(
            reverse_querystring("category-list", query_kwargs={"name": "3"}),
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["slug"] == "cat-3"
