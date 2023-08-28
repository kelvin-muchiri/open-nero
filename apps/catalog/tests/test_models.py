"""Models"""

from datetime import timedelta

from django.db import transaction
from django.db.utils import DataError, IntegrityError
from django.utils import timezone
from django_tenants.test.cases import FastTenantTestCase

from ..models import (
    Course,
    Deadline,
    Format,
    Level,
    Paper,
    Service,
    WriterType,
    WriterTypeService,
)


class LevelTestCase(FastTenantTestCase):
    """
    Tests for model Level
    """

    def setUp(self):
        self.level = Level.objects.create(name="TestLevel")

    def test_level_creation(self):
        """Ensure we can create a level object."""
        self.assertTrue(isinstance(self.level, Level))
        self.assertEqual(self.level.__str__(), self.level.name)


class CourseTestCase(FastTenantTestCase):
    """
    Tests for model Course
    """

    def setUp(self):
        self.course = Course.objects.create(name="TestCourse")

    def test_course_creation(self):
        """Ensure we can create a course object."""
        self.assertTrue(isinstance(self.course, Course))
        self.assertEqual(self.course.__str__(), self.course.name)


class PaperTestCase(FastTenantTestCase):
    """
    Tests for model Paper
    """

    def setUp(self):
        self.paper = Paper.objects.create(name="TestPaper")

    def test_paper_creation(self):
        """Ensure we can create a paper object."""
        self.assertTrue(isinstance(self.paper, Paper))
        self.assertEqual(self.paper.__str__(), self.paper.name)


class FormatTestCase(FastTenantTestCase):
    """
    Tests for model Format
    """

    def setUp(self):
        self.format = Format.objects.create(name="TestFormat")

    def test_format_creation(self):
        """Ensure we can create a format object."""
        self.assertTrue(isinstance(self.format, Format))
        self.assertEqual(self.format.__str__(), self.format.name)


class DeadlineTestCase(FastTenantTestCase):
    """
    Tests for model Deadline
    """

    def setUp(self):
        self.deadline_one_day = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.DAY
        )
        self.deadline_one_hour = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.HOUR
        )

    def test_deadline_creation(self):
        """Ensure we can create a deadline object."""
        self.assertTrue(isinstance(self.deadline_one_day, Deadline))
        self.assertEqual(
            self.deadline_one_day.__str__(), self.deadline_one_day.full_name
        )

    def test_deadline_full_name(self):
        """Ensure the full name for deadline object is correct."""
        deadline_two_days = Deadline.objects.create(
            value=2, deadline_type=Deadline.DeadlineType.DAY
        )
        deadline_two_hours = Deadline.objects.create(
            value=2, deadline_type=Deadline.DeadlineType.HOUR
        )

        self.assertEqual(self.deadline_one_day.full_name, "1 Day")
        self.assertEqual(deadline_two_days.full_name, "2 Days")
        self.assertEqual(self.deadline_one_hour.full_name, "1 Hour")
        self.assertEqual(deadline_two_hours.full_name, "2 Hours")

    def test_dealine_duration_day(self):
        """Ensure the duration for a deadline object of type DAY is correct."""
        self.assertEqual(self.deadline_one_day.duration, timedelta(days=1))

    def test_deadline_duration_hour(self):
        """Ensure the duration for a dealine object of type HOUR is correct."""
        self.assertEqual(self.deadline_one_hour.duration, timedelta(hours=1))

    def test_deadline_due_date_day(self):
        """Ensure the due date for a deadline object of type DAY is correct."""
        start = timezone.now()
        self.assertEqual(
            self.deadline_one_day.get_due_date(start), start + timedelta(days=1)
        )

    def test_deadline_due_date_hour(self):
        """Ensure that the due date for dedaline object of type HOUR is correct."""
        start = timezone.now()
        self.assertEqual(
            self.deadline_one_hour.get_due_date(start), start + timedelta(hours=1)
        )


class ServiceTestCase(FastTenantTestCase):
    """Tests for model Service"""

    def setUp(self):
        self.level = Level.objects.create(name="TestLevel")
        self.deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.DAY
        )
        self.paper = Paper.objects.create(name="TestPaper")
        self.service = Service.objects.create(
            level=self.level, deadline=self.deadline, paper=self.paper, amount=10.00
        )

    def test_creation(self):
        """Ensure we can create a Service object"""
        self.assertTrue(isinstance(self.service, Service))
        self.assertEqual(f"{self.service}", "TestPaper - TestLevel - 1 Day")
        self.assertEqual(self.service.level, self.level)
        self.assertEqual(self.service.deadline, self.deadline)
        self.assertEqual(self.service.paper, self.paper)
        self.assertEqual(self.service.amount, 10.00)

    def test_level_optional(self):
        """Ensure level is optional"""
        service = Service.objects.create(
            deadline=self.deadline, paper=self.paper, amount=5.00
        )
        self.assertEqual(service.level, None)

    def test_unique_together(self):
        """Ensure level, deadline and paper are unique"""
        with self.assertRaises(IntegrityError):
            Service.objects.create(
                level=self.level, deadline=self.deadline, paper=self.paper
            )


class WriterTypeTestCase(FastTenantTestCase):
    """Tests for model WriterType"""

    def setUp(self):
        self.writer_type = WriterType.objects.create(
            name="Test",
            sort_order=1,
            description="Awesome description here",
        )

    def test_creation(self):
        """Ensure we can create a WriterType object"""
        self.assertTrue(isinstance(self.writer_type, WriterType))
        self.assertEqual(f"{self.writer_type}", "Test")
        self.assertEqual(self.writer_type.name, "Test")
        self.assertEqual(self.writer_type.sort_order, 1)
        self.assertEqual(self.writer_type.description, "Awesome description here")

    def test_name_length(self):
        """Test name field does not exceed 32 chars"""
        # 33 chars raises error
        with transaction.atomic(), self.assertRaises(DataError):
            WriterType.objects.create(name="Lorem Ipsum is simply dummy texty")

        # 32 chars does not raise error
        WriterType.objects.create(name="Lorem Ipsum is simply dummy text")

    def test_description_length(self):
        """Test description field does not exceed 160 chars"""
        # 161 chars raises error
        with transaction.atomic(), self.assertRaises(DataError):
            WriterType.objects.create(
                name="Standard",
                description="""Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud""",
            )

        # 160 chars does not raise error
        WriterType.objects.create(
            name="Standard",
            description="""Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostru""",
        )

    def test_defaults(self):
        """Ensure the default fields for non required fields are correct"""
        writer_type = WriterType.objects.create(name="Test")
        self.assertEqual(writer_type.sort_order, 0)
        self.assertEqual(writer_type.description, None)


class WriterTypeServiceTestCase(FastTenantTestCase):
    """Tests for model Writer"""

    def setUp(self):
        level = Level.objects.create(name="TestLevel")
        deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.DAY
        )
        paper = Paper.objects.create(name="TestPaper")
        self.service = Service.objects.create(
            level=level, deadline=deadline, paper=paper, amount=5.00
        )
        self.writer_type = WriterType.objects.create(name="Premium")
        self.writer_type_service = WriterTypeService.objects.create(
            writer_type=self.writer_type, service=self.service, amount=10.00
        )

    def test_creation(self):
        """Ensure we can create a `WriterTypeService` object"""
        self.assertTrue(isinstance(self.writer_type_service, WriterTypeService))
        self.assertEqual(
            f"{self.writer_type_service}", "Premium - TestPaper - TestLevel - 1 Day"
        )
        self.assertEqual(self.writer_type_service.writer_type, self.writer_type)
        self.assertEqual(self.writer_type_service.service, self.service)

    def test_writer_type_service_unique(self):
        """Ensure write_type and service are unique together"""
        with self.assertRaises(IntegrityError):
            WriterTypeService.objects.create(
                writer_type=self.writer_type, service=self.service, amount=10.00
            )
