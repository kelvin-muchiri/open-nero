"""tests for views"""
import json
from datetime import timedelta
from unittest import mock

import dateutil
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.serializers.json import DjangoJSONEncoder
from django.http import SimpleCookie
from django.urls import reverse
from django.utils import timezone
from django_tenants.test.cases import FastTenantTestCase
from django_tenants.test.client import TenantClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.cart.models import Attachment, Cart, Item
from apps.catalog.models import (
    Course,
    Deadline,
    Format,
    Level,
    Paper,
    Service,
    WriterType,
    WriterTypeService,
)
from apps.coupon.models import Coupon
from apps.subscription.models import Subscription

User = get_user_model()


class GetCartTestCase(FastTenantTestCase):
    """Tests for GET cart"""

    def setUp(self):
        super().setUp()
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
        # Mock storage backends to prevent a file from being saved on disk
        self.file_name = "test.doc"
        self.patcher_1 = mock.patch("django.core.files.storage.FileSystemStorage.save")
        self.mock_file_storage_save = self.patcher_1.start()
        self.mock_file_storage_save.return_value = self.file_name
        self.patcher_2 = mock.patch("storages.backends.s3boto3.S3Boto3Storage.save")
        self.mock_s3_save = self.patcher_2.start()
        self.mock_s3_save.return_value = self.file_name
        # End mock

        self.client = TenantClient(self.tenant)
        self.owner = User.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
            is_email_verified=True,
        )
        self.cart, _ = Cart.objects.get_or_create(owner=self.owner)

    def tearDown(self):
        self.patcher_1.stop()
        self.patcher_2.stop()

    def get(self, user=None):
        """Method GET"""

        if user is None:
            user = self.owner
        self.client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(user).access_token}
        )
        return self.client.get(reverse("cart-list"))

    def test_authentication(self):
        """Ensure correct authentication."""
        response = self.client.get(reverse("cart-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_empty_cart(self):
        """Ensure empty cart returns"""
        response = self.get()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            json.dumps(response.data),
            json.dumps(
                {
                    "cart": {
                        "id": str(self.cart.pk),
                        "subtotal": "0",
                        "total": "0",
                        "discount": "0",
                        "coupon": None,
                        "items": [],
                        "best_match_coupon": None,
                    }
                }
            ),
        )

    @mock.patch("apps.cart.serializers.get_best_match_coupon")
    def test_cart_with_items(self, mock_best_match):
        """Ensure cart with items returns correctly"""
        mock_best_match.return_value = Coupon.objects.create(
            code="MOCKED",
            percent_off=5,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=1),
        )
        level = Level.objects.create(name="TestLevel")
        course = Course.objects.create(name="TestCourse")
        paper = Paper.objects.create(name="TestPaper")
        paper_format = Format.objects.create(name="TestFormat")
        deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.DAY
        )
        writer_type = WriterType.objects.create(name="Premium")
        item = Item.objects.create(
            cart=self.cart,
            topic="This is a topic",
            level=level,
            course=course,
            paper=paper,
            paper_format=paper_format,
            deadline=deadline,
            language=Item.Language.ENGLISH_UK,
            pages=3,
            references=1,
            quantity=2,
            page_price=10,
            writer_type=writer_type,
            writer_type_price=5,
        )
        file_field = SimpleUploadedFile(self.file_name, b"these are the file contents!")
        item.attachments.create(attachment=file_field)
        response = self.get()
        self.maxDiff = None
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            json.dumps(response.data, cls=DjangoJSONEncoder),
            json.dumps(
                {
                    "cart": {
                        "id": self.cart.pk,
                        "subtotal": "90.00",
                        "total": "90.00",
                        "discount": "0",
                        "coupon": None,
                        "items": [
                            {
                                "id": item.pk,
                                "topic": item.topic,
                                "level": {"id": level.pk, "name": level.name},
                                "course": {"id": course.pk, "name": course.name},
                                "paper": {"id": paper.pk, "name": paper.name},
                                "paper_format": {
                                    "id": paper_format.pk,
                                    "name": paper_format.name,
                                },
                                "deadline": {
                                    "id": deadline.pk,
                                    "full_name": deadline.full_name,
                                },
                                "language": {
                                    "id": item.language,
                                    "name": item.get_language_display(),
                                },
                                "pages": item.pages,
                                "references": item.references,
                                "comment": item.comment,
                                "quantity": item.quantity,
                                "price": f"{item.price}",
                                "total_price": f"{item.total_price}",
                                "writer_type": {
                                    "id": writer_type.pk,
                                    "name": writer_type.name,
                                    "description": writer_type.description,
                                },
                                "attachments": [
                                    {
                                        "id": item.attachments.first().pk,
                                        "filename": item.attachments.first().filename,
                                        "comment": item.attachments.first().comment,
                                    }
                                ],
                            }
                        ],
                        "best_match_coupon": {"code": "MOCKED", "discount": "4.50"},
                    }
                },
                cls=DjangoJSONEncoder,
            ),
        )

    def test_cart_with_discount(self):
        """Cart with coupon applied"""
        start_date = timezone.now()
        end_date = start_date + timedelta(days=1)
        coupon = Coupon.objects.create(
            percent_off=20, start_date=start_date, end_date=end_date
        )
        self.cart.coupon = coupon
        self.cart.save()
        level = Level.objects.create(name="TestLevel")
        course = Course.objects.create(name="TestCourse")
        paper = Paper.objects.create(name="TestPaper")
        paper_format = Format.objects.create(name="TestFormat")
        deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.DAY
        )
        item = Item.objects.create(
            cart=self.cart,
            topic="This is a topic",
            level=level,
            course=course,
            paper=paper,
            paper_format=paper_format,
            deadline=deadline,
            language=Item.Language.ENGLISH_UK,
            pages=3,
            references=1,
            quantity=1,
            page_price=10,
        )
        response = self.get()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            json.dumps(response.data, cls=DjangoJSONEncoder),
            json.dumps(
                {
                    "cart": {
                        "id": self.cart.pk,
                        "subtotal": "30.00",
                        "total": "24.00",
                        "discount": "6.00",
                        "coupon": {
                            "code": coupon.code,
                            "is_expired": coupon.is_expired,
                        },
                        "items": [
                            {
                                "id": item.pk,
                                "topic": item.topic,
                                "level": {"id": level.pk, "name": level.name},
                                "course": {"id": course.pk, "name": course.name},
                                "paper": {"id": paper.pk, "name": paper.name},
                                "paper_format": {
                                    "id": paper_format.pk,
                                    "name": paper_format.name,
                                },
                                "deadline": {
                                    "id": deadline.pk,
                                    "full_name": deadline.full_name,
                                },
                                "language": {
                                    "id": item.language,
                                    "name": item.get_language_display(),
                                },
                                "pages": item.pages,
                                "references": item.references,
                                "comment": item.comment,
                                "quantity": item.quantity,
                                "price": f"{item.price}",
                                "total_price": f"{item.total_price}",
                                "writer_type": None,
                                "attachments": [],
                            }
                        ],
                        "best_match_coupon": None,
                    }
                },
                cls=DjangoJSONEncoder,
            ),
        )

    def test_cart_owner(self):
        """Ensure cart belongs to logged in owner"""
        # Add a new user and cart for that user
        user = User.objects.create_user(
            username="testuser2",
            first_name="Test",
            email="testuser2@testdomain.com",
            password="12345",
            is_email_verified=True,
        )
        cart, _ = Cart.objects.get_or_create(owner=user)
        response = self.get(user)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Cart return should belong to testuser2
        self.assertEqual(response.data["cart"]["id"], str(cart.pk))


class CreateCartTestCase(FastTenantTestCase):
    """Tests for creating a new cart"""

    def setUp(self):
        super().setUp()
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
        self.level = Level.objects.create(name="TestLevel")
        self.course = Course.objects.create(name="TestCourse")
        self.paper = Paper.objects.create(name="TestPaper")
        self.paper_format = Format.objects.create(name="TestFormat")
        self.deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.DAY
        )
        self.service = Service.objects.create(
            deadline=self.deadline, level=self.level, paper=self.paper, amount=12
        )
        self.writer_type = WriterType.objects.create(name="Premium")
        WriterTypeService.objects.create(
            writer_type=self.writer_type, service=self.service, amount=5
        )
        self.client = TenantClient(self.tenant)
        self.user = User.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
            is_email_verified=True,
        )
        self.valid_payload = {
            "items": [
                {
                    "topic": "This is a topic",
                    "level": self.level.id,
                    "course": self.course.id,
                    "paper": self.paper.id,
                    "paper_format": self.paper_format.id,
                    "deadline": self.deadline.id,
                    "language": 1,
                    "pages": 2,
                    "references": 4,
                    "quantity": 2,
                    "writer_type": self.writer_type.id,
                    "comment": "Do a good job",
                }
            ]
        }

    def post(self, payload, user=None):
        """Method POST"""
        if user is None:
            user = self.user

        self.client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(user).access_token}
        )
        response = self.client.post(
            reverse("cart-list"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        return response

    def test_create_cart_authentication(self):
        """Ensure correct authentication when creating cart"""
        response = self.client.post(reverse("cart-list"), data={})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_valid_payload(self):
        """Ensure cart is created for valid payload"""
        response = self.post(self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cart = Cart.objects.filter(owner=self.user).first()
        self.assertEqual(
            response.data,
            {
                "id": str(cart.pk),
                "subtotal": "68.00",
                "total": "68.00",
                "discount": "0",
                "coupon": None,
                "items": [
                    {
                        "id": str(cart.items.all().first().pk),
                        "topic": "This is a topic",
                        "level": {
                            "id": str(self.level.pk),
                            "name": self.level.name,
                        },
                        "course": {
                            "id": str(self.course.pk),
                            "name": self.course.name,
                        },
                        "paper": {
                            "id": str(self.paper.pk),
                            "name": self.paper.name,
                        },
                        "paper_format": {
                            "id": str(self.paper_format.pk),
                            "name": self.paper_format.name,
                        },
                        "deadline": {
                            "id": str(self.deadline.pk),
                            "full_name": self.deadline.full_name,
                        },
                        "language": {"id": 1, "name": "English UK"},
                        "pages": 2,
                        "references": 4,
                        "comment": "Do a good job",
                        "quantity": 2,
                        "price": "34.00",
                        "total_price": "68.00",
                        "writer_type": {
                            "id": str(self.writer_type.pk),
                            "name": self.writer_type.name,
                            "description": self.writer_type.description,
                        },
                        "attachments": [],
                    }
                ],
                "best_match_coupon": None,
            },
        )

    def test_free_writer_type(self):
        """Cart is created with free writer type"""
        writer_type = WriterType.objects.create(name="Free")
        service = WriterTypeService.objects.create(
            writer_type=writer_type, service=self.service, amount=None
        )
        response = self.post(
            {
                "items": [
                    {
                        "topic": "This is a topic",
                        "level": self.level.id,
                        "course": self.course.id,
                        "paper": self.paper.id,
                        "paper_format": self.paper_format.id,
                        "deadline": self.deadline.id,
                        "language": 1,
                        "pages": 2,
                        "references": 4,
                        "quantity": 2,
                        "writer_type": writer_type.id,
                        "comment": "Do a good job",
                    }
                ]
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cart = Cart.objects.filter(owner=self.user).first()
        self.assertEqual(
            response.data,
            {
                "id": str(cart.pk),
                "subtotal": "48.00",
                "total": "48.00",
                "discount": "0",
                "coupon": None,
                "items": [
                    {
                        "id": str(cart.items.all().first().pk),
                        "topic": "This is a topic",
                        "level": {
                            "id": str(self.level.pk),
                            "name": self.level.name,
                        },
                        "course": {
                            "id": str(self.course.pk),
                            "name": self.course.name,
                        },
                        "paper": {
                            "id": str(self.paper.pk),
                            "name": self.paper.name,
                        },
                        "paper_format": {
                            "id": str(self.paper_format.pk),
                            "name": self.paper_format.name,
                        },
                        "deadline": {
                            "id": str(self.deadline.pk),
                            "full_name": self.deadline.full_name,
                        },
                        "language": {"id": 1, "name": "English UK"},
                        "pages": 2,
                        "references": 4,
                        "comment": "Do a good job",
                        "quantity": 2,
                        "price": "24.00",
                        "total_price": "48.00",
                        "writer_type": {
                            "id": str(writer_type.pk),
                            "name": writer_type.name,
                            "description": writer_type.description,
                        },
                        "attachments": [],
                    }
                ],
                "best_match_coupon": None,
            },
        )
        # test when entry is 0
        cart.delete()
        service.amount = 0.00
        service.save()
        response = self.post(
            {
                "items": [
                    {
                        "topic": "This is a topic",
                        "level": self.level.id,
                        "course": self.course.id,
                        "paper": self.paper.id,
                        "paper_format": self.paper_format.id,
                        "deadline": self.deadline.id,
                        "language": 1,
                        "pages": 2,
                        "references": 4,
                        "quantity": 2,
                        "writer_type": writer_type.id,
                        "comment": "Do a good job",
                    }
                ]
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cart = Cart.objects.filter(owner=self.user).first()
        self.assertEqual(
            response.data,
            {
                "id": str(cart.pk),
                "subtotal": "48.00",
                "total": "48.00",
                "discount": "0",
                "coupon": None,
                "items": [
                    {
                        "id": str(cart.items.all().first().pk),
                        "topic": "This is a topic",
                        "level": {
                            "id": str(self.level.pk),
                            "name": self.level.name,
                        },
                        "course": {
                            "id": str(self.course.pk),
                            "name": self.course.name,
                        },
                        "paper": {
                            "id": str(self.paper.pk),
                            "name": self.paper.name,
                        },
                        "paper_format": {
                            "id": str(self.paper_format.pk),
                            "name": self.paper_format.name,
                        },
                        "deadline": {
                            "id": str(self.deadline.pk),
                            "full_name": self.deadline.full_name,
                        },
                        "language": {"id": 1, "name": "English UK"},
                        "pages": 2,
                        "references": 4,
                        "comment": "Do a good job",
                        "quantity": 2,
                        "price": "24.00",
                        "total_price": "48.00",
                        "writer_type": {
                            "id": str(writer_type.pk),
                            "name": writer_type.name,
                            "description": writer_type.description,
                        },
                        "attachments": [],
                    }
                ],
                "best_match_coupon": None,
            },
        )

    def test_items_required(self):
        """Ensure items are required"""
        response = self.post({**self.valid_payload, "items": []})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_item_topic_required(self):
        """Test topic required for item"""
        response = self.post(
            {
                **self.valid_payload,
                "items": [
                    {
                        **self.valid_payload["items"][0],
                        "topic": "",
                    }
                ],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_item_course_required(self):
        """Test course is required for item"""
        response = self.post(
            {
                **self.valid_payload,
                "items": [
                    {
                        **self.valid_payload["items"][0],
                        "course": "",
                    }
                ],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_item_paper_required(self):
        """Test paper is required for item"""
        response = self.post(
            {
                **self.valid_payload,
                "items": [
                    {
                        **self.valid_payload["items"][0],
                        "paper": "",
                    }
                ],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_item_paper_format_required(self):
        """Test paper_format is required for item"""
        response = self.post(
            {
                **self.valid_payload,
                "items": [
                    {
                        **self.valid_payload["items"][0],
                        "paper_format": "",
                    }
                ],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_item_deadline_required(self):
        """Test deadline is required for item"""
        response = self.post(
            {
                **self.valid_payload,
                "items": [
                    {
                        **self.valid_payload["items"][0],
                        "deadline": "",
                    }
                ],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_item_language_optional(self):
        """Test language is optional for item

        Default language will be applied
        """
        response = self.post(
            {
                **self.valid_payload,
                "items": [
                    {
                        **self.valid_payload["items"][0],
                        "language": "",
                    }
                ],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cart = Cart.objects.filter(owner__username="testuser").first()
        self.assertEqual(cart.items.first().language, 1)

    def test_item_pages_optional(self):
        """Test pages is optional for item

        Default pages will be applied
        """
        response = self.post(
            {
                **self.valid_payload,
                "items": [
                    {
                        **self.valid_payload["items"][0],
                        "pages": "",
                    }
                ],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cart = Cart.objects.filter(owner__username="testuser").first()
        self.assertEqual(cart.items.first().pages, 1)

    def test_item_references_optional(self):
        """Test references is optional for item"""
        response = self.post(
            {
                **self.valid_payload,
                "items": [
                    {
                        **self.valid_payload["items"][0],
                        "references": "",
                    }
                ],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cart = Cart.objects.filter(owner__username="testuser").first()
        self.assertIsNone(cart.items.first().references)

    def test_item_comment_optional(self):
        """Test comment is optional for item"""
        response = self.post(
            {
                **self.valid_payload,
                "items": [
                    {
                        **self.valid_payload["items"][0],
                        "comment": "",
                    }
                ],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cart = Cart.objects.filter(owner__username="testuser").first()
        self.assertEqual(cart.items.first().comment, "")

    def test_item_quantity_optional(self):
        """Test quantity is optional for item

        Default quantity is applied"""
        response = self.post(
            {
                **self.valid_payload,
                "items": [
                    {
                        **self.valid_payload["items"][0],
                        "quantity": "",
                    }
                ],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cart = Cart.objects.filter(owner__username="testuser").first()
        self.assertEqual(cart.items.first().quantity, 1)

    def test_item_writer_type_optional(self):
        """Test writer_type is optional for item"""
        response = self.post(
            {
                **self.valid_payload,
                "items": [
                    {
                        **self.valid_payload["items"][0],
                        "writer_type": "",
                    }
                ],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cart = Cart.objects.filter(owner__username="testuser").first()
        self.assertEqual(cart.items.first().writer_type, None)
        # Confirm writer type charges are not included
        self.assertEqual(cart.total, 48.00)

    def test_item_level_optional(self):
        """Test level is not required for item"""
        # There exists a service where level is None
        service = Service.objects.create(
            deadline=self.deadline, paper=self.paper, amount=12
        )
        WriterTypeService.objects.create(
            writer_type=self.writer_type, service=service, amount=5
        )
        response = self.post(
            {
                **self.valid_payload,
                "items": [
                    {
                        **self.valid_payload["items"][0],
                        "level": "",
                    }
                ],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_item_quantity_max_min(self):
        """Ensure quantity falls within accepted range"""
        # Min should be 1
        response = self.post(
            {
                **self.valid_payload,
                "items": [
                    {
                        **self.valid_payload["items"][0],
                        "quantity": 0,
                    }
                ],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.post(
            {
                **self.valid_payload,
                "items": [
                    {
                        **self.valid_payload["items"][0],
                        "quantity": 1,
                    }
                ],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Max is 3
        response = self.post(
            {
                **self.valid_payload,
                "items": [
                    {
                        **self.valid_payload["items"][0],
                        "quantity": 4,
                    }
                ],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.post(
            {
                **self.valid_payload,
                "items": [
                    {
                        **self.valid_payload["items"][0],
                        "quantity": 3,
                    }
                ],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_item_pages_max_min(self):
        """Ensure pages falls within accepted range"""
        # Min should be 1
        response = self.post(
            {
                **self.valid_payload,
                "items": [
                    {
                        **self.valid_payload["items"][0],
                        "pages": 0,
                    }
                ],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.post(
            {
                **self.valid_payload,
                "items": [
                    {
                        **self.valid_payload["items"][0],
                        "pages": 1,
                    }
                ],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Max is 1000
        response = self.post(
            {
                **self.valid_payload,
                "items": [
                    {
                        **self.valid_payload["items"][0],
                        "pages": 1001,
                    }
                ],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.post(
            {
                **self.valid_payload,
                "items": [
                    {
                        **self.valid_payload["items"][0],
                        "pages": 1000,
                    }
                ],
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_service_availability(self):
        """Ensure service must be available"""
        level = Level.objects.create(name="TestLevel")
        paper = Paper.objects.create(name="TestPaper")
        deadline = Deadline.objects.create(
            value=2, deadline_type=Deadline.DeadlineType.DAY
        )
        payload = {
            **self.valid_payload,
            "items": [
                {
                    **self.valid_payload["items"][0],
                    "level": level.id,
                    "paper": paper.id,
                    "deadline": deadline.id,
                    "writer_type": "",
                }
            ],
        }

        # If service does not exist, we should not be able to create a cart
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # If service exists, the cart is created
        Service.objects.create(deadline=deadline, paper=paper, level=level, amount=12)
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_writer_type_availablity(self):
        """Ensure type of writer service is available"""
        level = Level.objects.create(name="TestLevel")
        paper = Paper.objects.create(name="TestPaper")
        deadline = Deadline.objects.create(
            value=2, deadline_type=Deadline.DeadlineType.DAY
        )
        service = Service.objects.create(
            deadline=deadline, paper=paper, level=level, amount=12
        )
        payload = {
            **self.valid_payload,
            "items": [
                {
                    **self.valid_payload["items"][0],
                    "level": level.id,
                    "paper": paper.id,
                    "deadline": deadline.id,
                    "writer_type": self.writer_type.id,
                }
            ],
        }
        # If service does not exist, we should not be able to create a cart
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # If service exists, the cart is created
        WriterTypeService.objects.create(
            writer_type=self.writer_type, service=service, amount=5
        )
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_service_priority(self):
        """Ensure a service with no level is given priority first"""
        service_without_level = Service.objects.create(
            deadline=self.deadline, paper=self.paper, amount=10.00
        )
        WriterTypeService.objects.create(
            writer_type=self.writer_type, service=service_without_level, amount=3
        )
        response = self.post(self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cart = Cart.objects.filter(owner__username="testuser").first()
        self.assertEqual(cart.total, 52.00)
        self.assertEqual(cart.items.first().page_price, 10.00)
        self.assertEqual(cart.items.first().writer_type_price, 3.00)


class RemoveSingleCartItemTestCase(FastTenantTestCase):
    """Tests for removing a single item from cart"""

    def setUp(self):
        self.client = TenantClient(self.tenant)
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
        self.owner = User.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
            is_email_verified=True,
        )
        self.level = Level.objects.create(name="TestLevel")
        self.course = Course.objects.create(name="TestCourse")
        self.paper = Paper.objects.create(name="TestPaper")
        self.paper_format = Format.objects.create(name="TestFormat")
        self.deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.DAY
        )
        self.cart, _ = Cart.objects.get_or_create(owner=self.owner)
        self.item_1 = Item.objects.create(
            cart=self.cart,
            topic="This is a topic",
            level=self.level,
            course=self.course,
            paper=self.paper,
            paper_format=self.paper_format,
            deadline=self.deadline,
            language=Item.Language.ENGLISH_UK,
            pages=3,
            references=1,
            quantity=2,
            page_price=15,
        )
        self.item_2 = Item.objects.create(
            cart=self.cart,
            topic="This is another topic",
            level=self.level,
            course=self.course,
            paper=self.paper,
            paper_format=self.paper_format,
            deadline=self.deadline,
            language=Item.Language.ENGLISH_UK,
            pages=3,
            references=1,
            quantity=2,
            page_price=15,
            comment="Awesome comment here",
        )
        self.valid_payload = {"item": self.item_1.id}

    def post(self, payload, user=None):
        """Method POST"""
        if user is None:
            user = self.owner

        self.client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(user).access_token}
        )
        cart = Cart.objects.get(owner=user)
        return self.client.post(
            reverse("cart-remove", kwargs={"pk": cart.pk}),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

    def test_authentication(self):
        """Ensure correct authentication"""
        response = self.client.post(
            reverse("cart-remove", kwargs={"pk": self.cart.pk}), data={}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_valid_payload(self):
        """Ensure removal of a valid item is correct"""
        # Before removal
        self.assertEqual(self.cart.total, 180.00)
        response = self.post(self.valid_payload)
        # After removal
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.cart.total, 90.00)
        self.assertEqual(
            response.data,
            {
                "id": str(self.cart.pk),
                "subtotal": "90.00",
                "total": "90.00",
                "discount": "0",
                "coupon": None,
                "items": [
                    {
                        "id": str(self.item_2.pk),
                        "topic": self.item_2.topic,
                        "level": {
                            "id": str(self.item_2.level.pk),
                            "name": self.item_2.level.name,
                        },
                        "course": {
                            "id": str(self.item_2.course.pk),
                            "name": self.item_2.course.name,
                        },
                        "paper": {
                            "id": str(self.item_2.paper.pk),
                            "name": self.item_2.paper.name,
                        },
                        "paper_format": {
                            "id": str(self.item_2.paper_format.pk),
                            "name": self.item_2.paper_format.name,
                        },
                        "deadline": {
                            "id": str(self.item_2.deadline.pk),
                            "full_name": self.item_2.deadline.full_name,
                        },
                        "language": {
                            "id": self.item_2.language,
                            "name": self.item_2.get_language_display(),
                        },
                        "pages": self.item_2.pages,
                        "references": self.item_2.references,
                        "comment": self.item_2.comment,
                        "quantity": self.item_2.quantity,
                        "price": str(self.item_2.price),
                        "total_price": str(self.item_2.total_price),
                        "writer_type": None,
                        "attachments": [],
                    }
                ],
                "best_match_coupon": None,
            },
        )

    def test_item_required(self):
        """Ensure `item` is required"""
        response = self.post({"item": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @mock.patch("apps.cart.views.is_coupon_valid")
    def test_invalid_coupon_removed(self, is_valid_mock):
        """If applied coupon becomes invalid when we remove an item, we remove it"""
        is_valid_mock.return_value = False
        owner = User.objects.create_user(
            username="coupon_invalid",
            first_name="Test",
            email="coupon_invalid@example.com",
            password="12345",
            is_email_verified=True,
        )
        coupon = Coupon.objects.create(
            code="COUP5",
            percent_off=5,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=1),
        )
        cart, _ = Cart.objects.get_or_create(owner=owner, coupon=coupon)
        item = Item.objects.create(
            cart=cart,
            topic="Test coupon invalid",
            level=self.level,
            course=self.course,
            paper=self.paper,
            paper_format=self.paper_format,
            deadline=self.deadline,
            language=Item.Language.ENGLISH_UK,
            pages=3,
            references=1,
            quantity=2,
            page_price=15,
        )
        self.assertIsNotNone(cart.coupon)
        response = self.post({"item": item.id}, owner)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cart.refresh_from_db()
        self.assertIsNone(cart.coupon)


class ClearCartTestCase(FastTenantTestCase):
    """Tests for clearing cart"""

    def setUp(self):
        self.client = TenantClient(self.tenant)
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
        self.owner = User.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
            is_email_verified=True,
        )
        self.level = Level.objects.create(name="TestLevel")
        self.course = Course.objects.create(name="TestCourse")
        self.paper = Paper.objects.create(name="TestPaper")
        self.paper_format = Format.objects.create(name="TestFormat")
        self.deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.DAY
        )
        self.cart, _ = Cart.objects.get_or_create(owner=self.owner)
        Item.objects.create(
            cart=self.cart,
            topic="This is a topic",
            level=self.level,
            course=self.course,
            paper=self.paper,
            paper_format=self.paper_format,
            deadline=self.deadline,
            language=Item.Language.ENGLISH_UK,
            pages=3,
            references=1,
            quantity=2,
            page_price=15,
        )

    def get(self, user=None):
        if user is None:
            user = self.owner

        self.client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(user).access_token}
        )
        cart = Cart.objects.get(owner=user)
        return self.client.get(reverse("cart-clear", kwargs={"pk": cart.pk}))

    def test_authentication(self):
        """Ensure correct authentication when clearing cart"""
        response = self.client.get(reverse("cart-clear", kwargs={"pk": self.cart.pk}))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_clear_cart(self):
        """Ensure clearing of a cart is correct"""
        # Before clear cart
        self.assertEqual(self.cart.total, 90.00)
        self.assertEqual(self.cart.items.all().count(), 1)
        response = self.get()
        # After clear cart
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.cart.total, 0.00)
        self.assertEqual(self.cart.items.all().count(), 0)
        self.assertEqual(
            response.data,
            {
                "id": str(self.cart.pk),
                "subtotal": "0",
                "total": "0",
                "discount": "0",
                "coupon": None,
                "items": [],
                "best_match_coupon": None,
            },
        )

    def test_coupon_removed(self):
        """Coupon is removed if cart cleared"""
        owner = User.objects.create_user(
            username="coupon_invalid",
            first_name="Test",
            email="coupon_invalid@example.com",
            password="12345",
            is_email_verified=True,
        )
        coupon = Coupon.objects.create(
            code="COUP5",
            percent_off=5,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=1),
        )
        cart, _ = Cart.objects.get_or_create(owner=owner, coupon=coupon)
        Item.objects.create(
            cart=cart,
            topic="Test coupon invalid",
            level=self.level,
            course=self.course,
            paper=self.paper,
            paper_format=self.paper_format,
            deadline=self.deadline,
            language=Item.Language.ENGLISH_UK,
            pages=3,
            references=1,
            quantity=2,
            page_price=15,
        )
        self.assertIsNotNone(cart.coupon)
        response = self.get(owner)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cart.refresh_from_db()
        self.assertIsNone(cart.coupon)


class GetSingleCartItemTestCase(FastTenantTestCase):
    """Tests for GET cart item"""

    def setUp(self):
        super().setUp()
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
        # Mock storage backends to prevent a file from being saved on disk
        self.file_name = "test.doc"
        self.patcher_1 = mock.patch("django.core.files.storage.FileSystemStorage.save")
        self.mock_file_storage_save = self.patcher_1.start()
        self.mock_file_storage_save.return_value = self.file_name
        self.patcher_2 = mock.patch("storages.backends.s3boto3.S3Boto3Storage.save")
        self.mock_s3_save = self.patcher_2.start()
        self.mock_s3_save.return_value = self.file_name
        file_field = SimpleUploadedFile(self.file_name, b"these are the file contents!")
        # End mock

        self.client = TenantClient(self.tenant)
        self.owner = User.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
            is_email_verified=True,
        )
        level = Level.objects.create(name="TestLevel")
        course = Course.objects.create(name="TestCourse")
        paper = Paper.objects.create(name="TestPaper")
        paper_format = Format.objects.create(name="TestFormat")
        deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.DAY
        )
        writer_type = WriterType.objects.create(name="Premium")
        self.cart, _ = Cart.objects.get_or_create(owner=self.owner)
        self.item_1 = Item.objects.create(
            cart=self.cart,
            topic="This is a topic",
            level=level,
            course=course,
            paper=paper,
            paper_format=paper_format,
            deadline=deadline,
            language=Item.Language.ENGLISH_UK,
            pages=3,
            references=1,
            quantity=2,
            page_price=15,
            writer_type=writer_type,
        )
        self.item_1_attachment = Attachment.objects.create(
            cart_item=self.item_1, attachment=file_field
        )

    def tearDown(self):
        self.patcher_1.stop()
        self.patcher_2.stop()

    def get(self, item_id, user=None):
        if user is None:
            user = self.owner

        self.client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(user).access_token}
        )
        return self.client.get(reverse("cart_item-detail", kwargs={"pk": item_id}))

    def test_authentication(self):
        """Ensure correct authentication"""
        response = self.client.get(
            reverse("cart_item-detail", kwargs={"pk": self.item_1.id})
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_valid_item(self):
        """Enure get valid cart item is correct"""
        response = self.get(self.item_1.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected = json.dumps(
            {
                "id": self.item_1.pk,
                "topic": self.item_1.topic,
                "level": self.item_1.level.pk,
                "course": self.item_1.course.pk,
                "paper": self.item_1.paper.pk,
                "paper_format": self.item_1.paper_format.pk,
                "deadline": self.item_1.deadline.pk,
                "language": self.item_1.language,
                "pages": self.item_1.pages,
                "references": self.item_1.references,
                "comment": self.item_1.comment,
                "quantity": self.item_1.quantity,
                "price": self.item_1.price,
                "total_price": self.item_1.total_price,
                "writer_type": self.item_1.writer_type.pk,
                "attachments": [
                    {
                        "id": self.item_1_attachment.pk,
                        "filename": self.item_1_attachment.filename,
                        "comment": self.item_1_attachment.comment,
                    }
                ],
            },
            cls=DjangoJSONEncoder,
        )
        self.assertEqual(json.dumps(response.data, cls=DjangoJSONEncoder), expected)

    def test_get_invalid_item(self):
        """Ensure get invalid single item is correct"""
        response = self.get(50)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class UpdateCartItemTestCase(FastTenantTestCase):
    """Tests for updating single cart item"""

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
        self.owner = User.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
            is_email_verified=True,
        )
        self.level = Level.objects.create(name="TestLevel")
        self.course = Course.objects.create(name="TestCourse")
        self.paper = Paper.objects.create(name="TestPaper")
        self.paper_format = Format.objects.create(name="TestFormat")
        self.deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.DAY
        )
        self.service = Service.objects.create(
            deadline=self.deadline, level=self.level, paper=self.paper, amount=12
        )
        self.writer_type = WriterType.objects.create(name="Premium")
        WriterTypeService.objects.create(
            writer_type=self.writer_type, service=self.service, amount=5
        )
        self.cart, _ = Cart.objects.get_or_create(owner=self.owner)
        self.item_1 = Item.objects.create(
            cart=self.cart,
            topic="This is a topic",
            level=self.level,
            course=self.course,
            paper=self.paper,
            paper_format=self.paper_format,
            deadline=self.deadline,
            language=Item.Language.ENGLISH_UK,
            pages=3,
            references=1,
            quantity=2,
            page_price=15,
            writer_type=self.writer_type,
            writer_type_price=5.00,
        )

    def put(self, item_id, payload, user=None):
        """Method PUT"""
        if user is None:
            user = self.owner

        self.client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(user).access_token}
        )
        return self.client.put(
            reverse("cart_item-detail", kwargs={"pk": item_id}),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

    def patch(self, item_id, payload, user=None):
        """Method PATCH"""
        if user is None:
            user = self.owner

        self.client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(user).access_token}
        )
        return self.client.patch(
            reverse("cart_item-detail", kwargs={"pk": item_id}),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

    def test_authentication(self):
        """Ensure correct authentication"""
        response = self.client.put(
            reverse("cart_item-detail", kwargs={"pk": self.item_1.pk}), data={}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_put(self):
        """Ensure put for valid payload works correctly"""
        level = Level.objects.create(name="Masters")
        course = Course.objects.create(name="Tourism")
        paper = Paper.objects.create(name="Dissertation")
        paper_format = Format.objects.create(name="APA")
        deadline = Deadline.objects.create(
            value=2, deadline_type=Deadline.DeadlineType.DAY
        )
        writer_type = WriterType.objects.create(name="Standard")
        service = Service.objects.create(
            deadline=deadline, level=level, paper=paper, amount=17
        )
        WriterTypeService.objects.create(
            writer_type=writer_type, service=service, amount=10
        )
        response = self.put(
            self.item_1.id,
            {
                "topic": "Updated topic",
                "level": level.id,
                "course": course.id,
                "paper": paper.id,
                "paper_format": paper_format.id,
                "deadline": deadline.id,
                "language": 2,
                "pages": 5,
                "references": 11,
                "comment": "Blah blah",
                "quantity": 3,
                "writer_type": writer_type.id,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item_1.refresh_from_db()
        self.assertEqual(self.item_1.topic, "Updated topic")
        self.assertEqual(self.item_1.level.id, level.id)
        self.assertEqual(self.item_1.course.id, course.id)
        self.assertEqual(self.item_1.paper.id, paper.id)
        self.assertEqual(self.item_1.paper_format.id, paper_format.id)
        self.assertEqual(self.item_1.deadline.id, deadline.id)
        self.assertEqual(self.item_1.language, 2)
        self.assertEqual(self.item_1.pages, 5)
        self.assertEqual(self.item_1.references, 11)
        self.assertEqual(self.item_1.comment, "Blah blah")
        self.assertEqual(self.item_1.quantity, 3)
        self.assertEqual(self.item_1.writer_type.id, writer_type.id)
        self.assertEqual(self.item_1.page_price, 17.00)
        self.assertEqual(self.item_1.writer_type_price, 10.00)

    def test_patch_topic(self):
        """Ensure topic is updated correctly"""
        response = self.patch(self.item_1.id, {"topic": "Updated topic"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item_1.refresh_from_db()
        self.assertEqual(self.item_1.topic, "Updated topic")

    def test_patch_level(self):
        """Ensure level is updated correctly"""
        level = Level.objects.create(name="Masters")
        # Add service for the new level
        service = Service.objects.create(
            deadline=self.deadline, level=level, paper=self.paper, amount=17
        )
        WriterTypeService.objects.create(
            writer_type=self.writer_type, service=service, amount=10
        )
        response = self.patch(self.item_1.id, {"level": level.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item_1.refresh_from_db()
        self.assertEqual(self.item_1.level.id, level.id)
        self.assertEqual(self.item_1.writer_type_price, 10.00)
        self.assertEqual(self.item_1.page_price, 17.00)

    def test_patch_course(self):
        """Ensure course is updated correctly"""
        course = Course.objects.create(name="Tourism")
        response = self.patch(self.item_1.id, {"course": course.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item_1.refresh_from_db()
        self.assertEqual(self.item_1.course.id, course.id)

    def test_patch_paper(self):
        """Ensure paper is updated correctly"""
        paper = Paper.objects.create(name="Dissertation")
        service = Service.objects.create(
            deadline=self.deadline, level=self.level, paper=paper, amount=16
        )
        WriterTypeService.objects.create(
            writer_type=self.writer_type, service=service, amount=8
        )
        response = self.patch(self.item_1.id, {"paper": paper.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item_1.refresh_from_db()
        self.assertEqual(self.item_1.paper.id, paper.id)
        self.assertEqual(self.item_1.writer_type_price, 8.00)
        self.assertEqual(self.item_1.page_price, 16.00)

    def test_patch_paper_format(self):
        """Ensure paper_format is updated correctly"""
        paper_format = Format.objects.create(name="APA")
        response = self.patch(self.item_1.id, {"paper_format": paper_format.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item_1.refresh_from_db()
        self.assertEqual(self.item_1.paper_format.id, paper_format.id)

    def test_patch_deadline(self):
        """Ensure deadline is updated correctly"""
        deadline = Deadline.objects.create(
            value=2, deadline_type=Deadline.DeadlineType.DAY
        )
        service = Service.objects.create(
            deadline=deadline, level=self.level, paper=self.paper, amount=10
        )
        WriterTypeService.objects.create(
            writer_type=self.writer_type, service=service, amount=7
        )
        response = self.patch(self.item_1.id, {"deadline": deadline.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item_1.refresh_from_db()
        self.assertEqual(self.item_1.deadline.id, deadline.id)
        self.assertEqual(self.item_1.writer_type_price, 7.00)
        self.assertEqual(self.item_1.page_price, 10.00)

    def test_patch_language(self):
        """Ensure language is updated correctly"""
        response = self.patch(self.item_1.id, {"language": 2})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item_1.refresh_from_db()
        self.assertEqual(self.item_1.language, 2)

    def test_patch_pages(self):
        """Ensure pages is updated correctly"""
        response = self.patch(self.item_1.id, {"pages": 5})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item_1.refresh_from_db()
        self.assertEqual(self.item_1.pages, 5)

    def test_patch_references(self):
        """Ensure references is updated correctly"""
        response = self.patch(self.item_1.id, {"references": 7})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item_1.refresh_from_db()
        self.assertEqual(self.item_1.references, 7)

    def test_patch_comment(self):
        """Ensure comment is updated correctly"""
        comment = "I will send materials later"
        response = self.patch(self.item_1.id, {"comment": comment})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item_1.refresh_from_db()
        self.assertEqual(self.item_1.comment, comment)

    def test_patch_quantity(self):
        """Ensure quantity is updated correctly"""
        response = self.patch(self.item_1.id, {"quantity": 1})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item_1.refresh_from_db()
        self.assertEqual(self.item_1.quantity, 1)

        # Test add to quantity
        response = self.patch(self.item_1.id, {"quantity": 1, "update_quantity": False})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item_1.refresh_from_db()
        self.assertEqual(self.item_1.quantity, 2)

    def test_patch_writer_type(self):
        """Ensure writer_type is updated correctly"""
        writer_type = WriterType.objects.create(name="Standard")
        WriterTypeService.objects.create(
            writer_type=writer_type, service=self.service, amount=4
        )
        response = self.patch(self.item_1.id, {"writer_type": writer_type.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item_1.refresh_from_db()
        self.assertEqual(self.item_1.writer_type.id, writer_type.id)
        self.assertEqual(self.item_1.writer_type_price, 4.00)

    def test_topic_required(self):
        """Test topic required"""
        response = self.patch(self.item_1.id, {"topic": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_course_required(self):
        """Test course is required"""
        response = self.patch(self.item_1.id, {"course": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_paper_required(self):
        """Test paper is required"""
        response = self.patch(self.item_1.id, {"paper": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_paper_format_required(self):
        """Test paper_format is required"""
        response = self.patch(self.item_1.id, {"paper_format": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_deadline_required(self):
        """Test deadline is required"""
        response = self.patch(self.item_1.id, {"deadline": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_level_optional(self):
        """Test level is not required"""
        # There exists a service where level is None
        service = Service.objects.create(
            deadline=self.deadline, paper=self.paper, amount=20
        )
        WriterTypeService.objects.create(
            writer_type=self.writer_type, service=service, amount=3
        )
        response = self.patch(self.item_1.id, {"level": ""})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item_1.refresh_from_db()
        self.assertEqual(self.item_1.level, None)
        self.assertEqual(self.item_1.page_price, 20.00)
        self.assertEqual(self.item_1.writer_type_price, 3.00)

    def test_item_writer_type_optional(self):
        """Test writer_type is optional for item"""
        response = self.patch(self.item_1.id, {"writer_type": ""})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item_1.refresh_from_db()
        self.assertEqual(self.item_1.writer_type, None)
        self.assertEqual(self.item_1.writer_type_price, None)

    def test_item_quantity_max_min(self):
        """Ensure quantity falls within accepted range"""
        # Min should be 1
        response = self.patch(self.item_1.id, {"quantity": 0})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.patch(self.item_1.id, {"quantity": 1})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Max is 3
        response = self.patch(self.item_1.id, {"quantity": 4})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.patch(self.item_1.id, {"quantity": 3})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_item_pages_max_min(self):
        """Ensure pages falls within accepted range"""
        # Min should be 1
        response = self.patch(self.item_1.id, {"pages": 0})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.patch(self.item_1.id, {"pages": 1})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Max is 1000
        response = self.patch(self.item_1.id, {"pages": 1001})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.patch(self.item_1.id, {"pages": 1000})
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class DeleteCartItemTestCase(FastTenantTestCase):
    """Tests for DELETE single cart item"""

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
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
        self.owner = User.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
            is_email_verified=True,
        )
        level = Level.objects.create(name="TestLevel")
        course = Course.objects.create(name="TestCourse")
        paper = Paper.objects.create(name="TestPaper")
        paper_format = Format.objects.create(name="TestFormat")
        deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.DAY
        )
        service = Service.objects.create(
            deadline=deadline, level=level, paper=paper, amount=12
        )
        writer_type = WriterType.objects.create(name="Premium")
        WriterTypeService.objects.create(
            writer_type=writer_type, service=service, amount=5
        )
        self.cart, _ = Cart.objects.get_or_create(owner=self.owner)
        self.item_1 = Item.objects.create(
            cart=self.cart,
            topic="This is a topic",
            level=level,
            course=course,
            paper=paper,
            paper_format=paper_format,
            deadline=deadline,
            language=Item.Language.ENGLISH_UK,
            pages=3,
            references=1,
            quantity=2,
            page_price=15,
        )

    def delete(self, item_id, user=None):
        """Method DELETE"""
        if user is None:
            user = self.owner

        self.client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(user).access_token}
        )
        return self.client.delete(
            reverse("cart_item-detail", kwargs={"pk": item_id}),
            content_type="application/json",
        )

    def test_authentication(self):
        """Ensure correct authentication."""
        response = self.client.delete(
            reverse("cart_item-detail", kwargs={"pk": self.item_1.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_not_allowed(self):
        """Ensure that the creation of a single cart item is not allowed"""
        response = self.delete(self.item_1.pk)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class UploadAttachmentTestCase(FastTenantTestCase):
    """Tests for uploading attachment"""

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
        # Mock storage backends to prevent a file from being saved on disk
        self.file_name = "test.doc"
        self.patcher_1 = mock.patch("django.core.files.storage.FileSystemStorage.save")
        self.mock_file_storage_save = self.patcher_1.start()
        self.mock_file_storage_save.return_value = self.file_name
        self.patcher_2 = mock.patch("storages.backends.s3boto3.S3Boto3Storage.save")
        self.mock_s3_save = self.patcher_2.start()
        self.mock_s3_save.return_value = self.file_name
        # End mock

        self.owner = User.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
            is_email_verified=True,
        )
        self.level = Level.objects.create(name="TestLevel")
        self.course = Course.objects.create(name="TestCourse")
        self.paper = Paper.objects.create(name="TestPaper")
        self.paper_format = Format.objects.create(name="TestFormat")
        self.deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.DAY
        )
        self.service = Service.objects.create(
            deadline=self.deadline, level=self.level, paper=self.paper, amount=12
        )
        self.writer_type = WriterType.objects.create(name="Premium")
        WriterTypeService.objects.create(
            writer_type=self.writer_type, service=self.service, amount=5
        )
        self.cart, _ = Cart.objects.get_or_create(owner=self.owner)
        self.item_1 = Item.objects.create(
            cart=self.cart,
            topic="This is a topic",
            level=self.level,
            course=self.course,
            paper=self.paper,
            paper_format=self.paper_format,
            deadline=self.deadline,
            language=Item.Language.ENGLISH_UK,
            pages=3,
            references=1,
            quantity=2,
            page_price=15,
            writer_type=self.writer_type,
            writer_type_price=5.00,
        )
        self.file_field = SimpleUploadedFile(
            self.file_name, b"these are the file contents!"
        )
        self.valid_payload = {
            "cart_item": f"{self.item_1.id}",
            "attachment": self.file_field,
            "comment": "Use paragraph 1 and 2",
        }

    def tearDown(self):
        self.patcher_1.stop()
        self.patcher_2.stop()

    def post(self, payload, user=None):
        """Method POST"""

        if user is None:
            user = self.owner

        self.client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(user).access_token}
        )
        return self.client.post(reverse("cart_attachment-list"), data=payload)

    def test_authentication(self):
        """Ensure correct authentication"""
        response = self.client.post(
            reverse("cart_attachment-list"), data=self.valid_payload
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_valid_payload(self):
        """Ensure `Attachment` is created for valid payload"""
        response = self.post(self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.item_1.attachments.count(), 1)

    def test_cart_item_required(self):
        """Ensure `cart_item` field is required"""
        response = self.post({**self.valid_payload, "cart_item": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_attachment_required(self):
        """Ensure `attachment` field is required"""
        response = self.post({**self.valid_payload, "attachment": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_comment_optional(self):
        """Ensure comment is not required"""
        response = self.post({**self.valid_payload, "comment": ""})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_comment_length(self):
        """Ensure the comment length is correct"""
        # 255 chars
        comment = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolorui"
        self.assertEqual(len(comment), 255)
        response = self.post({**self.valid_payload, "comment": comment})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # 256 chars
        comment = comment + "k"
        self.assertEqual(len(comment), 256)
        response = self.post({**self.valid_payload, "comment": comment})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_max_files(self):
        """Ensure maximum files for item is not exceeded"""
        # Ensure default of 6 is not exceeded
        attachments = []
        for _ in range(7):
            attachments.append(
                Attachment(cart_item=self.item_1, attachment=self.file_field)
            )

        Attachment.objects.bulk_create(attachments)
        response = self.post(self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class DeleteAttachmentTestCase(FastTenantTestCase):
    """Tests for deleting a single attachment"""

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
        # Mock storage backends to prevent a file from being saved on disk
        self.file_name = "test.doc"
        self.patcher_1 = mock.patch("django.core.files.storage.FileSystemStorage.save")
        self.mock_file_storage_save = self.patcher_1.start()
        self.mock_file_storage_save.return_value = self.file_name

        self.patcher_2 = mock.patch("storages.backends.s3boto3.S3Boto3Storage.save")
        self.mock_s3_save = self.patcher_2.start()
        self.mock_s3_save.return_value = self.file_name

        self.patcher_3 = mock.patch("storages.backends.s3boto3.S3Boto3Storage.delete")
        self.mock_s3_delete = self.patcher_3.start()

        self.patcher_4 = mock.patch(
            "django.core.files.storage.FileSystemStorage.delete"
        )
        self.mock_file_storage_delete = self.patcher_4.start()
        # End mock

        self.owner = User.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
            is_email_verified=True,
        )
        self.level = Level.objects.create(name="TestLevel")
        self.course = Course.objects.create(name="TestCourse")
        self.paper = Paper.objects.create(name="TestPaper")
        self.paper_format = Format.objects.create(name="TestFormat")
        self.deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.DAY
        )
        self.service = Service.objects.create(
            deadline=self.deadline, level=self.level, paper=self.paper, amount=12
        )
        self.writer_type = WriterType.objects.create(name="Premium")
        WriterTypeService.objects.create(
            writer_type=self.writer_type, service=self.service, amount=5
        )
        self.cart, _ = Cart.objects.get_or_create(owner=self.owner)
        self.item_1 = Item.objects.create(
            cart=self.cart,
            topic="This is a topic",
            level=self.level,
            course=self.course,
            paper=self.paper,
            paper_format=self.paper_format,
            deadline=self.deadline,
            language=Item.Language.ENGLISH_UK,
            pages=3,
            references=1,
            quantity=2,
            page_price=15,
            writer_type=self.writer_type,
            writer_type_price=5.00,
        )
        self.file_field = SimpleUploadedFile(
            self.file_name, b"these are the file contents!"
        )
        self.attachment = Attachment.objects.create(
            cart_item=self.item_1, attachment=self.file_field, comment="Use paragraph 1"
        )

    def tearDown(self):
        self.patcher_1.stop()
        self.patcher_2.stop()
        self.patcher_3.stop()
        self.patcher_4.stop()

    def delete(self, item_id, user=None):
        if user is None:
            user = self.owner

        self.client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(user).access_token}
        )
        return self.client.delete(
            reverse("cart_attachment-detail", kwargs={"pk": item_id})
        )

    def test_authentication(self):
        """Ensure correct authentication"""
        response = self.client.delete(
            reverse("cart_attachment-detail", kwargs={"pk": self.attachment.id}),
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_deletion(self):
        """Ensure we can delete an `Attachment`"""
        response = self.delete(self.attachment.id)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Attachment.objects.count(), 0)


@mock.patch("apps.cart.views.create_presigned_url")
class DownloadAttachmentTestCase(FastTenantTestCase):
    """Tests for downloading an attachment"""

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
        # Mock storage backends to prevent a file from being saved on disk
        self.file_name = "test.doc"
        self.patcher_2 = mock.patch("django.core.files.storage.FileSystemStorage.save")
        self.mock_file_storage_save = self.patcher_2.start()
        self.mock_file_storage_save.return_value = self.file_name
        self.patcher_3 = mock.patch("storages.backends.s3boto3.S3Boto3Storage.save")
        self.mock_s3_save = self.patcher_3.start()
        self.mock_s3_save.return_value = self.file_name
        # End mock

        self.owner = User.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
            is_email_verified=True,
        )
        self.level = Level.objects.create(name="TestLevel")
        self.course = Course.objects.create(name="TestCourse")
        self.paper = Paper.objects.create(name="TestPaper")
        self.paper_format = Format.objects.create(name="TestFormat")
        self.deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.DAY
        )
        self.service = Service.objects.create(
            deadline=self.deadline, level=self.level, paper=self.paper, amount=12
        )
        self.writer_type = WriterType.objects.create(name="Premium")
        WriterTypeService.objects.create(
            writer_type=self.writer_type, service=self.service, amount=5
        )
        self.cart, _ = Cart.objects.get_or_create(owner=self.owner)
        self.item_1 = Item.objects.create(
            cart=self.cart,
            topic="This is a topic",
            level=self.level,
            course=self.course,
            paper=self.paper,
            paper_format=self.paper_format,
            deadline=self.deadline,
            language=Item.Language.ENGLISH_UK,
            pages=3,
            references=1,
            quantity=2,
            page_price=15,
            writer_type=self.writer_type,
            writer_type_price=5.00,
        )
        self.file_field = SimpleUploadedFile(
            "test.doc", b"these are the file contents!"
        )
        self.attachment = Attachment.objects.create(
            cart_item=self.item_1, attachment=self.file_field, comment="Use paragraph 1"
        )
        self.payload = {"attachment": self.attachment.id}

    def tearDown(self):
        self.patcher_2.stop()
        self.patcher_3.stop()

    def post(self, payload, user=None):
        """Method POST"""
        if user is None:
            user = self.owner

        self.client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(user).access_token}
        )
        response = self.client.post(
            reverse("cart_item-download-attachment", kwargs={"pk": self.item_1.pk}),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        return response

    def test_authentication(self, mock_create_signed_url):
        """Ensure correct authentication"""
        mock_create_signed_url.return_value = "https://s3.amazaon.com/signed-url/"
        response = self.client.post(
            reverse("cart_item-download-attachment", kwargs={"pk": self.item_1.pk}),
            data={},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_valid_payload(self, mock_create_signed_url):
        """Ensure we can download an attachment for valid payload"""
        mock_create_signed_url.return_value = "https://s3.amazaon.com/signed-url/"
        response = self.post(self.payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"url": "https://s3.amazaon.com/signed-url/"})

    def test_failure(self, mock_create_signed_url):
        """Returns 500 status code if download fails"""
        mock_create_signed_url.return_value = None
        response = self.post(self.payload)
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_attachment_required(self, mock_create_signed_url):
        """Ensure `attachment` field is required"""
        mock_create_signed_url.return_value = "https://s3.amazaon.com/signed-url/"
        response = self.post({"attachment": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_attachment_id(self, mock_create_signed_url):
        """Ensure `attachment` should be a valid id"""
        mock_create_signed_url.return_value = "https://s3.amazaon.com/signed-url/"
        response = self.post({"attachment": "1223"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
