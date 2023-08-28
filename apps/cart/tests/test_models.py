"""tests for models"""

from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DataError, transaction
from django.db.utils import IntegrityError
from django.utils import timezone
from django_tenants.test.cases import FastTenantTestCase

from apps.cart.models import Attachment, Cart, Item
from apps.catalog.models import Course, Deadline, Format, Level, Paper, WriterType
from apps.coupon.models import Coupon

User = get_user_model()

# pylint: disable=too-many-instance-attributes


class CartTestCase(FastTenantTestCase):
    """Tests for model Cart"""

    def setUp(self):
        super().setUp()

        self.level = Level.objects.create(name="TestLevel")
        self.course = Course.objects.create(name="TestCourse")
        self.paper = Paper.objects.create(name="TestPaper")
        self.paper_format = Format.objects.create(name="TestFormat")
        self.deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.DAY
        )
        self.writer_type = WriterType.objects.create(name="Premium")
        start_date = timezone.now()
        end_date = start_date + timedelta(days=1)
        coupon = Coupon.objects.create(
            percent_off=20, start_date=start_date, end_date=end_date
        )
        self.cart = Cart.objects.create(
            owner=User.objects.create_user(
                username="testuser",
                first_name="Test",
                email="testuser@testdomain.com",
                password="12345",
            ),
            coupon=coupon,
        )
        Item.objects.create(
            cart=self.cart,
            topic="First topic",
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
            writer_type_price=20.00,
        )
        Item.objects.create(
            cart=self.cart,
            topic="Second topic",
            level=self.level,
            course=self.course,
            paper=self.paper,
            paper_format=self.paper_format,
            deadline=self.deadline,
            language=Item.Language.ENGLISH_UK,
            pages=3,
            references=1,
            quantity=1,
            page_price=10,
            writer_type=self.writer_type,
            writer_type_price=30.00,
        )

    def test_creation(self):
        """Ensure we can create a `Cart` object"""
        self.assertTrue(isinstance(self.cart, Cart))
        self.assertEqual(f"{self.cart}", "Test")
        self.assertEqual(self.cart.owner.username, "testuser")
        self.assertEqual(list(self.cart.items.all()), list(Item.objects.all()))

    def test_cart_total(self):
        """Ensure the cart total is correct"""
        # Cart with items and coupon
        self.assertEqual(self.cart.total, 264.00)

        # Cart with items and no coupon
        cart_no_coupon = Cart.objects.create(
            owner=User.objects.create_user(
                username="cart_no_coupon",
                first_name="Test",
                email="itemsnodiscount@example.com",
                password="12345",
            ),
        )
        Item.objects.create(
            cart=cart_no_coupon,
            topic="First topic",
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
            writer_type_price=20.00,
        )
        self.assertEqual(cart_no_coupon.total, 210)

        # Cart with expired coupon
        start_date = timezone.now() - timedelta(days=10)
        end_date = timezone.now() - timedelta(days=2)
        coupon_expired = Coupon.objects.create(
            percent_off=20, start_date=start_date, end_date=end_date
        )
        cart_coupon_expired = Cart.objects.create(
            owner=User.objects.create_user(
                username="cart_coupon_expired",
                first_name="Test",
                email="cart_coupon_expired@example.com",
                password="12345",
            ),
            coupon=coupon_expired,
        )
        Item.objects.create(
            cart=cart_coupon_expired,
            topic="First topic",
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
            writer_type_price=20.00,
        )
        self.assertEqual(cart_coupon_expired.total, 210)

        # Cart with no items
        cart = Cart.objects.create(
            owner=User.objects.create_user(
                username="testuser2",
                first_name="Test2",
                email="testuser2@testdomain.com",
                password="12345",
            )
        )
        self.assertEqual(cart.total, 0.00)

    def test_coupon_delete(self):
        """Deleting a coupon does not delete cart"""
        start_date = timezone.now()
        end_date = start_date + timedelta(days=1)
        coupon = Coupon.objects.create(
            percent_off=20, start_date=start_date, end_date=end_date
        )
        cart = Cart.objects.create(
            owner=User.objects.create_user(
                username="cart_coupon_delete",
                first_name="Test",
                email="cart_coupon_delete@example.com",
                password="12345",
            ),
            coupon=coupon,
        )
        Item.objects.create(
            cart=cart,
            topic="First topic",
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
            writer_type_price=20.00,
        )
        # before deleting cart
        self.assertEqual(cart.total, 168)

        coupon.delete()

        # after deleting cart
        cart.refresh_from_db()
        self.assertIsNone(cart.coupon)
        self.assertEqual(cart.total, 210)


class ItemTestCase(FastTenantTestCase):
    """Tests for model Item"""

    def setUp(self):
        super().setUp()

        self.level = Level.objects.create(name="TestLevel")
        self.course = Course.objects.create(name="TestCourse")
        self.paper = Paper.objects.create(name="TestPaper")
        self.paper_format = Format.objects.create(name="TestFormat")
        self.deadline = Deadline.objects.create(
            value=2, deadline_type=Deadline.DeadlineType.DAY
        )
        self.writer_type = WriterType.objects.create(name="Premium")
        self.cart = Cart.objects.create(
            owner=User.objects.create_user(
                username="testuser",
                first_name="Test",
                email="testuser@testdomain.com",
                password="12345",
            )
        )
        self.item = Item.objects.create(
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
            writer_type_price=20.00,
        )

    def test_item_creation(self):
        """Ensure we can create an `Item` object"""
        self.assertTrue(isinstance(self.item, Item))
        self.assertEqual(f"{self.item}", "TestPaper - This is a topic")
        self.assertEqual(self.item.cart, self.cart)
        self.assertEqual(self.item.topic, "This is a topic")
        self.assertEqual(self.item.level, self.level)
        self.assertEqual(self.item.course, self.course)
        self.assertEqual(self.item.paper, self.paper)
        self.assertEqual(self.item.paper_format, self.paper_format)
        self.assertEqual(self.item.deadline, self.deadline)
        self.assertEqual(self.item.language, Item.Language.ENGLISH_UK)
        self.assertEqual(self.item.pages, 3)
        self.assertEqual(self.item.references, 1)
        self.assertEqual(self.item.quantity, 2)
        self.assertEqual(self.item.page_price, 15.00)
        self.assertEqual(self.item.writer_type, self.writer_type)
        self.assertEqual(self.item.writer_type_price, 20.00)

    def test_unit_price(self):
        """Ensure the item unit price is correct"""
        self.assertEqual(self.item.price, 105.00)

    def test_total_price(self):
        """Ensure the item total price is correct"""
        self.assertEqual(self.item.total_price, 210.00)

    def test_level_optional(self):
        """Ensure `level` is not required"""
        item = Item.objects.create(
            cart=self.cart,
            topic="Level is optional",
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
            writer_type_price=20.00,
        )
        self.assertEqual(item.level, None)

    def test_writer_type_optional(self):
        """Ensure `writer_type` and `writer_price` optional"""
        item = Item.objects.create(
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
        self.assertEqual(item.writer_type, None)
        self.assertEqual(item.writer_type_price, None)
        self.assertEqual(item.price, 45.00)
        self.assertEqual(item.total_price, 90.00)

    def test_quantity_default(self):
        """Ensure the default value for `quantity` is correct"""
        item = Item.objects.create(
            cart=self.cart,
            topic="This is a topic",
            level=self.level,
            course=self.course,
            paper=self.paper,
            paper_format=self.paper_format,
            deadline=self.deadline,
            language=Item.Language.ENGLISH_UK,
            pages=1000,
            references=1,
            page_price=15,
        )
        self.assertEqual(item.quantity, 1)

    def test_pages_default(self):
        """Ensure the default value for `pages` is correct"""
        item = Item.objects.create(
            cart=self.cart,
            topic="This is a topic",
            level=self.level,
            course=self.course,
            paper=self.paper,
            paper_format=self.paper_format,
            deadline=self.deadline,
            language=Item.Language.ENGLISH_UK,
            references=1,
            page_price=15,
        )
        self.assertEqual(item.pages, 1)

    def test_pages_positive(self):
        """Ensure `pages` should be a positive integer"""
        with transaction.atomic(), self.assertRaises(IntegrityError):
            Item.objects.create(
                cart=self.cart,
                topic="This is a topic",
                level=self.level,
                course=self.course,
                paper=self.paper,
                paper_format=self.paper_format,
                deadline=self.deadline,
                language=Item.Language.ENGLISH_UK,
                references=1,
                page_price=15,
                pages=-1,
            )

    def test_quantity_positive(self):
        """Ensure `quantity` should be a positive integer"""
        with transaction.atomic(), self.assertRaises(IntegrityError):
            Item.objects.create(
                cart=self.cart,
                topic="This is a topic",
                level=self.level,
                course=self.course,
                paper=self.paper,
                paper_format=self.paper_format,
                deadline=self.deadline,
                language=Item.Language.ENGLISH_UK,
                references=1,
                page_price=15,
                quantity=-1,
            )


class AttachmentTestCase(FastTenantTestCase):
    """Add tests for model `Attachment`"""

    def setUp(self):
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
        self.cart = Cart.objects.create(
            owner=User.objects.create_user(
                username="testuser",
                first_name="Test",
                email="testuser@testdomain.com",
                password="12345",
            )
        )
        level = Level.objects.create(name="TestLevel")
        course = Course.objects.create(name="TestCourse")
        paper = Paper.objects.create(name="TestPaper")
        paper_format = Format.objects.create(name="TestFormat")
        deadline = Deadline.objects.create(
            value=3, deadline_type=Deadline.DeadlineType.DAY
        )
        writer_type = WriterType.objects.create(name="Premium")
        self.item = Item.objects.create(
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
            writer_type_price=20.00,
        )
        self.file_field = SimpleUploadedFile(
            self.file_name, b"these are the file contents!"
        )

    def tearDown(self):
        self.patcher_1.stop()
        self.patcher_2.stop()

    def test_creation(self):
        """Ensure we can create a `Attachment`"""
        attachment = Attachment.objects.create(
            cart_item=self.item,
            attachment=self.file_field,
            comment="Do not forget to rate",
        )
        self.assertEqual(f"{attachment}", f"{self.item} - {attachment.attachment.name}")
        self.assertEqual(attachment.attachment.name, self.file_name)
        self.assertEqual(attachment.comment, "Do not forget to rate")
        self.assertEqual(attachment.filename, "test.doc")

    def test_comment_length(self):
        """Ensure the comment length is correct"""
        # Comment should not exceed 255
        comment = "Lorem ipsum dolor sit amet, consectetur \
        adipiscing elit, sed do eiusmod tempor incididunt \
        ut labore et dolore magna aliqua. Ut enim ad minim \
        veniam, quis nostrud exercitation ullamco laboris nisi \
        ut aliquip ex ea commodo consequat. Duis aute irure dolor in"

        with transaction.atomic(), self.assertRaises(DataError):
            # 256 chars
            Attachment.objects.create(
                cart_item=self.item,
                attachment=self.file_field,
                comment=comment,
            )

        # Does not raise error if comment is 255 chars
        Attachment.objects.create(
            cart_item=self.item,
            attachment=self.file_field,
            comment=comment[:255],
        )

    def test_comment_can_be_null(self):
        """Ensure `comment` field can be null"""
        attachment = Attachment.objects.create(
            cart_item=self.item,
            attachment=self.file_field,
        )
        self.assertEqual(attachment.comment, None)
