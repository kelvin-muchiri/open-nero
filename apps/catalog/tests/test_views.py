import json
from datetime import timedelta

import dateutil
import pytest
from django.core.serializers.json import DjangoJSONEncoder
from django.http import SimpleCookie
from django.urls import reverse
from django.utils import timezone
from django_tenants.test.cases import FastTenantTestCase
from django_tenants.test.client import TenantClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.utils import reverse_querystring
from apps.coupon.models import Coupon
from apps.orders.models import Order
from apps.subscription.models import Subscription
from apps.users.models import User

from ..models import (
    Course,
    Deadline,
    Format,
    Level,
    Paper,
    Service,
    WriterType,
    WriterTypeService,
    WriterTypeTag,
)


@pytest.mark.django_db
class TestGetLevels:
    """Tests for get levels"""

    @pytest.fixture
    def create_levels(self):
        paper = Paper.objects.create(name="Thesis")
        level_1 = Level.objects.create(name="High School", sort_order=0)
        level_2 = Level.objects.create(name="Undergraduate", sort_order=1)
        level_3 = Level.objects.create(name="Masters", sort_order=2)
        deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.DAY
        )
        Service.objects.create(
            level=level_1, deadline=deadline, paper=paper, amount=5.00
        )
        Service.objects.create(
            level=level_3, deadline=deadline, paper=paper, amount=5.00
        )

        return locals()

    def test_authentication(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        response = fast_tenant_client.get(reverse("level-list"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_staff_user(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_levels,
        store_staff,
        create_active_subscription,
    ):
        """Returns response for staff user"""
        level_1 = create_levels["level_1"]
        level_2 = create_levels["level_2"]
        level_3 = create_levels["level_3"]
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.get(reverse("level-list"))
        assert response.status_code == status.HTTP_200_OK
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            [
                {
                    "id": str(level_1.pk),
                    "name": level_1.name,
                    "sort_order": level_1.sort_order,
                },
                {
                    "id": str(level_2.pk),
                    "name": level_2.name,
                    "sort_order": level_2.sort_order,
                },
                {
                    "id": str(level_3.pk),
                    "name": level_3.name,
                    "sort_order": level_3.sort_order,
                },
            ],
            cls=DjangoJSONEncoder,
        )

    def test_only_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Non staff users cannot get all levels"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.get(reverse("level-list"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_paper_filter(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_levels,
        store_staff,
        create_active_subscription,
    ):
        """Ensure that `paper` query param filter works"""
        level_1 = create_levels["level_1"]
        level_3 = create_levels["level_3"]
        paper = create_levels["paper"]
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.get(
            reverse_querystring("level-list", query_kwargs={"paper": paper.pk})
        )
        assert response.status_code == status.HTTP_200_OK
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            [
                {
                    "id": str(level_1.pk),
                    "name": level_1.name,
                    "sort_order": level_1.sort_order,
                },
                {
                    "id": str(level_3.pk),
                    "name": level_3.name,
                    "sort_order": level_3.sort_order,
                },
            ],
            cls=DjangoJSONEncoder,
        )


@pytest.mark.django_db
class TestCreateLevel:
    """Tests for create level"""

    valid_payload = {"name": "Masters", "sort_order": 1}

    def test_auth_required(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        response = fast_tenant_client.post(reverse("level-list"), data={})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """Store staff can create academic level"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.post(
            reverse("level-list"), data=TestCreateLevel.valid_payload
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_only_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Non-staff is not allowed to create level"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.post(
            reverse("level-list"), data=TestCreateLevel.valid_payload
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_name_required(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """name is required"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.post(
            reverse("level-list"), data={"sort_order": 1}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response = fast_tenant_client.post(
            reverse("level-list"), data={"name": "", "sort_order": 1}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestUpdateLevel:
    """Tests for update level"""

    def test_auth_required(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        level = Level.objects.create(name="High School", sort_order=0)
        response = fast_tenant_client.put(
            reverse("level-detail", kwargs={"pk": level.pk}), data={}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_valid_payload(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """Updates level"""
        level = Level.objects.create(name="High School", sort_order=0)
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.put(
            reverse("level-detail", kwargs={"pk": level.pk}),
            data=json.dumps(
                {"name": "Doctorate", "sort_order": 7}, cls=DjangoJSONEncoder
            ),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        level.refresh_from_db()
        assert level.name == "Doctorate"
        assert level.sort_order == 7

    def test_only_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Non-staff users cannot update"""
        level = Level.objects.create(name="Undergraduate", sort_order=0)
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.put(
            reverse("level-detail", kwargs={"pk": level.pk}),
            data=json.dumps(
                {"name": "Doctorate", "sort_order": 7}, cls=DjangoJSONEncoder
            ),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_name_required(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """name is required"""
        level = Level.objects.create(name="High School", sort_order=0)

        # blank is not allowed
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.put(
            reverse("level-detail", kwargs={"pk": level.pk}),
            data=json.dumps({"name": "", "sort_order": 7}, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # none is not allowed
        response = fast_tenant_client.put(
            reverse("level-detail", kwargs={"pk": level.pk}),
            data=json.dumps({"sort_order": 7}, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestDeleteLevel:
    """Tests for delete level"""

    def test_auth_required(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        level = Level.objects.create(name="High School", sort_order=0)

        response = fast_tenant_client.delete(
            reverse("level-detail", kwargs={"pk": level.pk})
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_valid_level(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """Deletes level"""
        level = Level.objects.create(name="High School", sort_order=0)
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.delete(
            reverse("level-detail", kwargs={"pk": level.pk})
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Level.objects.filter(name="High School").count() == 0

    def test_only_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Non-staff users cannot delete"""
        level = Level.objects.create(name="Undergraduate", sort_order=0)
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.delete(
            reverse("level-detail", kwargs={"pk": level.pk})
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestGetCourses:
    """Tests for get courses"""

    @pytest.fixture()
    def create_courses(self):
        course_1 = Course.objects.create(name="Tourism", sort_order=3)
        course_2 = Course.objects.create(name="Business", sort_order=1)
        course_3 = Course.objects.create(name="Nursing", sort_order=0)

        return locals()

    def test_get_all_courses(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_courses,
        create_active_subscription,
    ):
        """Ensure response for GET all courses is correct"""
        course_1 = create_courses["course_1"]
        course_2 = create_courses["course_2"]
        course_3 = create_courses["course_3"]
        response = fast_tenant_client.get(reverse("course-list"))
        assert response.status_code == status.HTTP_200_OK
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            [
                {
                    "id": str(course_3.pk),
                    "name": course_3.name,
                    "sort_order": course_3.sort_order,
                },
                {
                    "id": str(course_2.pk),
                    "name": course_2.name,
                    "sort_order": course_2.sort_order,
                },
                {
                    "id": str(course_1.pk),
                    "name": course_1.name,
                    "sort_order": course_1.sort_order,
                },
            ],
            cls=DjangoJSONEncoder,
        )


@pytest.mark.django_db
class TestCreateCourse:
    """Tests for create course"""

    valid_payload = {"name": "Nursing", "sort_order": 1}

    def test_auth_required(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        response = fast_tenant_client.post(reverse("course-list"), data={})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_valid_payload(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """Valid payload creates course"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.post(
            reverse("course-list"), data=TestCreateCourse.valid_payload
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_non_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Non-staff user is not allowed to create"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.post(
            reverse("course-list"), data=TestCreateCourse.valid_payload
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_name_required(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """name is required"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.post(
            reverse("course-list"),
            data={"name": "", "sort_order": 1},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response = fast_tenant_client.post(
            reverse("course-list"), data={"sort_order": 1}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestUpdateCourse:
    """Tests for update course"""

    def test_auth_required(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        course = Course.objects.create(name="Tourism", sort_order=0)
        response = fast_tenant_client.put(
            reverse("course-detail", kwargs={"pk": course.pk}), data={}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_valid_payload(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """Updates successfully"""
        course = Course.objects.create(name="Tourism", sort_order=0)
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.put(
            reverse("course-detail", kwargs={"pk": course.pk}),
            data=json.dumps(
                {"name": "Mathematics", "sort_order": 7}, cls=DjangoJSONEncoder
            ),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        course.refresh_from_db()
        assert course.name == "Mathematics"
        assert course.sort_order == 7

    def test_only_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Non-staff users cannot update"""
        course = Course.objects.create(name="Business", sort_order=0)
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.put(
            reverse("course-detail", kwargs={"pk": course.pk}),
            data=json.dumps(
                {"name": "Mathematics", "sort_order": 7}, cls=DjangoJSONEncoder
            ),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_name_required(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """name is required"""
        course = Course.objects.create(name="Business", sort_order=0)

        # blank is not allowed
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.put(
            reverse("course-detail", kwargs={"pk": course.pk}),
            data=json.dumps({"name": "", "sort_order": 7}, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # none is not allowed
        response = fast_tenant_client.put(
            reverse("course-detail", kwargs={"pk": course.pk}),
            data=json.dumps({"sort_order": 7}, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestDeleteCourse:
    """Tests for delete course"""

    def test_auth_required(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        course = Course.objects.create(name="Tourism", sort_order=0)

        response = fast_tenant_client.delete(
            reverse("course-detail", kwargs={"pk": course.pk})
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_valid_course(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """Deletes course"""
        course = Course.objects.create(name="Tourism", sort_order=0)
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.delete(
            reverse("course-detail", kwargs={"pk": course.pk})
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Course.objects.filter(name="Tourism").count() == 0

    def test_only_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Non-staff users cannot delete"""
        course = Course.objects.create(name="Tourism", sort_order=0)
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.delete(
            reverse("course-detail", kwargs={"pk": course.pk})
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestGetFormats:
    """Tests for get formats"""

    @pytest.fixture()
    def create_formats(self):
        format_1 = Format.objects.create(name="APA", sort_order=3)
        format_2 = Format.objects.create(name="Chicago", sort_order=1)
        format_3 = Format.objects.create(name="MLA", sort_order=0)

        return locals()

    def test_get_all_formats(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_formats,
        create_active_subscription,
    ):
        """Ensure response for GET all formats is correct"""
        format_1 = create_formats["format_1"]
        format_2 = create_formats["format_2"]
        format_3 = create_formats["format_3"]
        response = fast_tenant_client.get(reverse("format-list"))
        assert response.status_code == status.HTTP_200_OK
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            [
                {
                    "id": str(format_3.pk),
                    "name": format_3.name,
                    "sort_order": format_3.sort_order,
                },
                {
                    "id": str(format_2.pk),
                    "name": format_2.name,
                    "sort_order": format_2.sort_order,
                },
                {
                    "id": str(format_1.pk),
                    "name": format_1.name,
                    "sort_order": format_1.sort_order,
                },
            ],
            cls=DjangoJSONEncoder,
        )


@pytest.mark.django_db
class TestCreateFormat:
    """Tests for create academic level"""

    valid_payload = {"name": "MLA", "sort_order": 1}

    def test_auth_required(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        response = fast_tenant_client.post(reverse("format-list"), data={})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_valid_payload(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """Valid payload creates format"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.post(
            reverse("format-list"), data=TestCreateFormat.valid_payload
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_non_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Non-staff user is not allowed to create"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.post(
            reverse("format-list"), data=TestCreateFormat.valid_payload
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_name_required(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """name is required"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.post(
            reverse("format-list"), data={"name": "", "sort_order": 1}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response = fast_tenant_client.post(
            reverse("format-list"), data={"sort_order": 1}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestUpdateFormat:
    """Tests for update format"""

    def test_auth_required(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        format = Format.objects.create(name="APA", sort_order=0)
        response = fast_tenant_client.put(
            reverse("format-detail", kwargs={"pk": format.pk}), data={}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_valid_payload(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """Updates successfully"""
        format = Format.objects.create(name="APA", sort_order=0)
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.put(
            reverse("format-detail", kwargs={"pk": format.pk}),
            data=json.dumps(
                {"name": "Mathematics", "sort_order": 7}, cls=DjangoJSONEncoder
            ),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        format.refresh_from_db()
        assert format.name == "Mathematics"
        assert format.sort_order == 7

    def test_only_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Non-staff users cannot update"""
        format = Format.objects.create(name="Chicago", sort_order=0)
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.put(
            reverse("format-detail", kwargs={"pk": format.pk}),
            data=json.dumps(
                {"name": "Mathematics", "sort_order": 7}, cls=DjangoJSONEncoder
            ),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_name_required(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """name is required"""
        format = Format.objects.create(name="Chicago", sort_order=0)

        # blank is not allowed
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.put(
            reverse("format-detail", kwargs={"pk": format.pk}),
            data=json.dumps({"name": "", "sort_order": 7}, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # none is not allowed
        response = fast_tenant_client.put(
            reverse("format-detail", kwargs={"pk": format.pk}),
            data=json.dumps({"sort_order": 7}, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestDeleteFormat:
    """Tests for delete format"""

    def test_auth_required(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        format = Format.objects.create(name="APA", sort_order=0)

        response = fast_tenant_client.delete(
            reverse("format-detail", kwargs={"pk": format.pk})
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_valid_format(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """Deletes format"""
        format = Format.objects.create(name="APA", sort_order=0)
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.delete(
            reverse("format-detail", kwargs={"pk": format.pk})
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Format.objects.filter(name="APA").count() == 0

    def test_only_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Non-staff users cannot delete"""
        format = Format.objects.create(name="APA", sort_order=0)
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.delete(
            reverse("format-detail", kwargs={"pk": format.pk})
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestGetDeadlines:
    """Tests for get deadlines"""

    @pytest.fixture()
    def create_deadlines(self):
        deadline_1 = Deadline.objects.create(
            value=2, deadline_type=Deadline.DeadlineType.DAY, sort_order=1
        )
        deadline_2 = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.DAY, sort_order=1
        )
        deadline_3 = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.HOUR, sort_order=0
        )
        deadline_4 = Deadline.objects.create(
            value=2, deadline_type=Deadline.DeadlineType.HOUR, sort_order=0
        )
        paper = Paper.objects.create(name="Thesis")
        level = Level.objects.create(name="High School", sort_order=0)
        Service.objects.create(
            level=level, deadline=deadline_2, paper=paper, amount=5.00
        )
        Service.objects.create(
            level=level, deadline=deadline_3, paper=paper, amount=5.00
        )

        return locals()

    def test_authentication(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        response = fast_tenant_client.get(reverse("deadline-list"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_staff_user(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_deadlines,
        store_staff,
        create_active_subscription,
    ):
        """Returns response for staff user"""
        deadline_1 = create_deadlines["deadline_1"]
        deadline_2 = create_deadlines["deadline_2"]
        deadline_3 = create_deadlines["deadline_3"]
        deadline_4 = create_deadlines["deadline_4"]
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.get(reverse("deadline-list"))
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            [
                {
                    "id": str(deadline_3.pk),
                    "full_name": deadline_3.full_name,
                    "value": deadline_3.value,
                    "deadline_type": deadline_3.deadline_type,
                    "sort_order": deadline_3.sort_order,
                },
                {
                    "id": str(deadline_4.pk),
                    "full_name": deadline_4.full_name,
                    "value": deadline_4.value,
                    "deadline_type": deadline_4.deadline_type,
                    "sort_order": deadline_4.sort_order,
                },
                {
                    "id": str(deadline_2.pk),
                    "full_name": deadline_2.full_name,
                    "value": deadline_2.value,
                    "deadline_type": deadline_2.deadline_type,
                    "sort_order": deadline_2.sort_order,
                },
                {
                    "id": str(deadline_1.pk),
                    "full_name": deadline_1.full_name,
                    "value": deadline_1.value,
                    "deadline_type": deadline_1.deadline_type,
                    "sort_order": deadline_1.sort_order,
                },
            ],
            cls=DjangoJSONEncoder,
        )

    def test_only_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Non staff users cannot get deadlines"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.get(reverse("deadline-list"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_filters_work(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_deadlines,
        create_active_subscription,
    ):
        """Filters work"""
        deadline_2 = create_deadlines["deadline_2"]
        deadline_3 = create_deadlines["deadline_3"]
        paper = create_deadlines["paper"]
        level = create_deadlines["level"]

        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.get(
            reverse_querystring("deadline-list", query_kwargs={"paper": paper.pk})
        )

        assert response.status_code == status.HTTP_200_OK
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            [
                {
                    "id": str(deadline_3.pk),
                    "full_name": deadline_3.full_name,
                    "value": deadline_3.value,
                    "deadline_type": deadline_3.deadline_type,
                    "sort_order": deadline_3.sort_order,
                },
                {
                    "id": str(deadline_2.pk),
                    "full_name": deadline_2.full_name,
                    "value": deadline_2.value,
                    "deadline_type": deadline_2.deadline_type,
                    "sort_order": deadline_2.sort_order,
                },
            ],
            cls=DjangoJSONEncoder,
        )

        response = fast_tenant_client.get(
            reverse_querystring("deadline-list", query_kwargs={"level": level.pk})
        )

        assert response.status_code == status.HTTP_200_OK
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            [
                {
                    "id": str(deadline_3.pk),
                    "full_name": deadline_3.full_name,
                    "value": deadline_3.value,
                    "deadline_type": deadline_3.deadline_type,
                    "sort_order": deadline_3.sort_order,
                },
                {
                    "id": str(deadline_2.pk),
                    "full_name": deadline_2.full_name,
                    "value": deadline_2.value,
                    "deadline_type": deadline_2.deadline_type,
                    "sort_order": deadline_2.sort_order,
                },
            ],
            cls=DjangoJSONEncoder,
        )


@pytest.mark.django_db
class TestCreateDeadline:
    """Tests for create academic level"""

    valid_payload = {"value": 1, "deadline_type": 1, "sort_order": 0}

    def test_auth_required(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        response = fast_tenant_client.post(reverse("deadline-list"), data={})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_valid_payload(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """Valid payload creates deadline"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.post(
            reverse("deadline-list"), data=TestCreateDeadline.valid_payload
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_non_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Non-staff user is not allowed to create"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.post(
            reverse("deadline-list"), data=TestCreateDeadline.valid_payload
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_value_required(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """value is required"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.post(
            reverse("deadline-list"),
            data={"value": "", "deadline_type": 1, "sort_order": 1},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response = fast_tenant_client.post(
            reverse("deadline-list"), data={"deadline_type": 1, "sort_order": 1}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestUpdateDeadline:
    """Tests for update deadline"""

    def test_auth_required(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.HOUR, sort_order=0
        )
        response = fast_tenant_client.put(
            reverse("deadline-detail", kwargs={"pk": deadline.pk}), data={}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_valid_payload(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """Updates successfully"""
        deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.HOUR, sort_order=0
        )
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.put(
            reverse("deadline-detail", kwargs={"pk": deadline.pk}),
            data=json.dumps(
                {
                    "value": 2,
                    "deadline_type": Deadline.DeadlineType.DAY,
                    "sort_order": 7,
                },
                cls=DjangoJSONEncoder,
            ),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        deadline.refresh_from_db()
        assert deadline.value == 2
        assert deadline.deadline_type == Deadline.DeadlineType.DAY
        assert deadline.sort_order == 7

    def test_only_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Non-staff users cannot update"""
        deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.HOUR, sort_order=0
        )
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.put(
            reverse("deadline-detail", kwargs={"pk": deadline.pk}),
            data=json.dumps(
                {
                    "value": 2,
                    "deadline_type": Deadline.DeadlineType.DAY,
                    "sort_order": 7,
                },
                cls=DjangoJSONEncoder,
            ),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_value_required(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """value is required"""
        deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.HOUR, sort_order=0
        )

        # blank is not allowed
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.put(
            reverse("deadline-detail", kwargs={"pk": deadline.pk}),
            data=json.dumps(
                {
                    "value": "",
                    "deadline_type": Deadline.DeadlineType.DAY,
                    "sort_order": 7,
                },
                cls=DjangoJSONEncoder,
            ),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # none is not allowed
        response = fast_tenant_client.put(
            reverse("deadline-detail", kwargs={"pk": deadline.pk}),
            data=json.dumps(
                {
                    "deadline_type": Deadline.DeadlineType.DAY,
                    "sort_order": 7,
                },
                cls=DjangoJSONEncoder,
            ),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestDeleteDeadline:
    """Tests for delete deadline"""

    def test_auth_required(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.HOUR, sort_order=0
        )

        response = fast_tenant_client.delete(
            reverse("deadline-detail", kwargs={"pk": deadline.pk})
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_valid_deadline(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """Deletes deadline"""
        deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.HOUR, sort_order=0
        )
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.delete(
            reverse("deadline-detail", kwargs={"pk": deadline.pk})
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert (
            Deadline.objects.filter(
                value=1, deadline_type=Deadline.DeadlineType.HOUR
            ).count()
            == 0
        )

    def test_only_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Non-staff users cannot delete"""
        deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.HOUR, sort_order=0
        )
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.delete(
            reverse("deadline-detail", kwargs={"pk": deadline.pk})
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestDeadlineExists:
    """Tests for deadline exists check"""

    @pytest.fixture()
    def create_deadlines(self):
        deadline_1 = Deadline.objects.create(
            value=2, deadline_type=Deadline.DeadlineType.DAY, sort_order=1
        )

        return locals()

    def test_authentication(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        response = fast_tenant_client.post(reverse("deadline-exists"), data={})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_staff_user(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_deadlines,
        store_staff,
        create_active_subscription,
    ):
        """Returns response for staff user"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.post(
            reverse("deadline-exists"),
            data={"value": 2, "deadline_type": 2},
        )
        assert response.status_code == status.HTTP_200_OK
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            {"exists": True},
            cls=DjangoJSONEncoder,
        )
        # if deadline does not exists, it returns false
        response = fast_tenant_client.post(
            reverse("deadline-exists"),
            data={"value": 3, "deadline_type": 2},
        )
        assert response.status_code == status.HTTP_200_OK
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            {"exists": False},
            cls=DjangoJSONEncoder,
        )

    def test_only_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Non staff users cannot get deadlines"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.post(reverse("deadline-exists"), data={})
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestGetPapers:
    """Tests for get papers"""

    @pytest.fixture
    def create_papers(self):
        paper_1 = Paper.objects.create(name="Thesis", sort_order=3)
        paper_2 = Paper.objects.create(name="Dissertaion", sort_order=0)  # no service
        paper_3 = Paper.objects.create(name="Admission Essay", sort_order=2)
        paper_4 = Paper.objects.create(
            name="Annotated Bibliography", sort_order=1
        )  # no level
        level_1 = Level.objects.create(name="College", sort_order=6)
        level_2 = Level.objects.create(name="Masters", sort_order=5)
        deadline_1 = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.DAY
        )
        deadline_2 = Deadline.objects.create(
            value=2, deadline_type=Deadline.DeadlineType.DAY
        )
        deadline_3 = Deadline.objects.create(
            value=3, deadline_type=Deadline.DeadlineType.DAY
        )
        Service.objects.create(
            level=level_2, deadline=deadline_2, paper=paper_1, amount=5.00
        )
        Service.objects.create(
            level=level_1, deadline=deadline_2, paper=paper_3, amount=5.00
        )
        Service.objects.create(deadline=deadline_1, paper=paper_4, amount=5.00)
        Service.objects.create(deadline=deadline_3, paper=paper_4, amount=5.00)  # paper
        # 4 has another deadline

        return locals()

    def test_get_service_paper_only(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_papers,
        create_active_subscription,
    ):
        """Returns only papers that have a service"""
        paper_1 = create_papers["paper_1"]
        paper_3 = create_papers["paper_3"]
        paper_4 = create_papers["paper_4"]
        level_1 = create_papers["level_1"]
        level_2 = create_papers["level_2"]
        deadline_1 = create_papers["deadline_1"]
        deadline_2 = create_papers["deadline_2"]
        deadline_3 = create_papers["deadline_3"]

        response = fast_tenant_client.get(
            reverse_querystring("paper-list", query_kwargs={"service_only": True})
        )

        assert response.status_code == status.HTTP_200_OK
        # should only return papers that have an associated service
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            [
                {
                    "id": str(paper_4.pk),
                    "name": paper_4.name,
                    "sort_order": paper_4.sort_order,
                    "levels": [],  # if no levels specified show deadlines
                    "deadlines": [
                        {
                            "id": str(deadline_1.pk),
                            "full_name": str(deadline_1.full_name),
                        },
                        {
                            "id": str(deadline_3.pk),
                            "full_name": str(deadline_3.full_name),
                        },
                    ],
                },
                {
                    "id": str(paper_3.pk),
                    "name": paper_3.name,
                    "sort_order": paper_3.sort_order,
                    "levels": [
                        {
                            "id": str(level_1.pk),
                            "name": level_1.name,
                            "deadlines": [
                                {
                                    "id": str(deadline_2.pk),
                                    "full_name": deadline_2.full_name,
                                },
                            ],
                        }
                    ],
                    "deadlines": [],  # if levels available do not display paper deadlines
                },
                {
                    "id": str(paper_1.pk),
                    "name": paper_1.name,
                    "sort_order": paper_1.sort_order,
                    "levels": [
                        {
                            "id": str(level_2.pk),
                            "name": level_2.name,
                            "deadlines": [
                                {
                                    "id": str(deadline_2.pk),
                                    "full_name": deadline_2.full_name,
                                },
                            ],
                        }
                    ],
                    "deadlines": [],  # if levels available do not display paper dealines
                },
            ],
            cls=DjangoJSONEncoder,
        )

    def test_get_all_papers(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_papers,
        create_active_subscription,
    ):
        """Returns all papers even the ones have no service"""
        paper_1 = create_papers["paper_1"]
        paper_2 = create_papers["paper_2"]
        paper_3 = create_papers["paper_3"]
        paper_4 = create_papers["paper_4"]
        level_1 = create_papers["level_1"]
        level_2 = create_papers["level_2"]
        deadline_1 = create_papers["deadline_1"]
        deadline_2 = create_papers["deadline_2"]
        deadline_3 = create_papers["deadline_3"]

        response = fast_tenant_client.get(reverse("paper-list"))

        assert response.status_code == status.HTTP_200_OK
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            [
                {
                    "id": str(paper_2.pk),
                    "name": paper_2.name,
                    "sort_order": paper_2.sort_order,
                    "levels": [],
                    "deadlines": [],
                },
                {
                    "id": str(paper_4.pk),
                    "name": paper_4.name,
                    "sort_order": paper_4.sort_order,
                    "levels": [],  # if no levels specified show deadlines
                    "deadlines": [
                        {
                            "id": str(deadline_1.pk),
                            "full_name": str(deadline_1.full_name),
                        },
                        {
                            "id": str(deadline_3.pk),
                            "full_name": str(deadline_3.full_name),
                        },
                    ],
                },
                {
                    "id": str(paper_3.pk),
                    "name": paper_3.name,
                    "sort_order": paper_3.sort_order,
                    "levels": [
                        {
                            "id": str(level_1.pk),
                            "name": level_1.name,
                            "deadlines": [
                                {
                                    "id": str(deadline_2.pk),
                                    "full_name": deadline_2.full_name,
                                },
                            ],
                        }
                    ],
                    "deadlines": [],  # if levels available do not display paper deadlines
                },
                {
                    "id": str(paper_1.pk),
                    "name": paper_1.name,
                    "sort_order": paper_1.sort_order,
                    "levels": [
                        {
                            "id": str(level_2.pk),
                            "name": level_2.name,
                            "deadlines": [
                                {
                                    "id": str(deadline_2.pk),
                                    "full_name": deadline_2.full_name,
                                },
                            ],
                        }
                    ],
                    "deadlines": [],  # if levels available do not display paper dealines
                },
            ],
            cls=DjangoJSONEncoder,
        )


@pytest.mark.django_db
class TestCreatePaper:
    """Tests for create paper"""

    valid_payload = {"name": "Admission Essay", "sort_order": 1}

    def test_auth_required(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        response = fast_tenant_client.post(reverse("paper-list"), data={})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_valid_payload(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """Valid payload creates paper"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.post(
            reverse("paper-list"), data=TestCreatePaper.valid_payload
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_non_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Non-staff user is not allowed to create"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.post(
            reverse("paper-list"), data=TestCreatePaper.valid_payload
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_name_required(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """name is required"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.post(
            reverse("paper-list"), data={"name": "", "sort_order": 1}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response = fast_tenant_client.post(
            reverse("paper-list"), data={"sort_order": 1}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestUpdatePaper:
    """Tests for update paper"""

    def test_auth_required(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        paper = Paper.objects.create(name="Thesis", sort_order=0)
        response = fast_tenant_client.put(
            reverse("paper-detail", kwargs={"pk": paper.pk}), data={}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_valid_payload(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """Updates successfully"""
        paper = Paper.objects.create(name="Thesis", sort_order=0)
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.put(
            reverse("paper-detail", kwargs={"pk": paper.pk}),
            data=json.dumps(
                {"name": "Mathematics", "sort_order": 7}, cls=DjangoJSONEncoder
            ),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        paper.refresh_from_db()
        assert paper.name == "Mathematics"
        assert paper.sort_order == 7

    def test_only_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Non-staff users cannot update"""
        paper = Paper.objects.create(name="Business", sort_order=0)
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.put(
            reverse("paper-detail", kwargs={"pk": paper.pk}),
            data=json.dumps(
                {"name": "Mathematics", "sort_order": 7}, cls=DjangoJSONEncoder
            ),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_name_required(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """name is required"""
        paper = Paper.objects.create(name="Business", sort_order=0)

        # blank is not allowed
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.put(
            reverse("paper-detail", kwargs={"pk": paper.pk}),
            data=json.dumps({"name": "", "sort_order": 7}, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # none is not allowed
        response = fast_tenant_client.put(
            reverse("paper-detail", kwargs={"pk": paper.pk}),
            data=json.dumps({"sort_order": 7}, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestDeletePaper:
    """Tests for delete paper"""

    def test_auth_required(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        paper = Paper.objects.create(name="Thesis", sort_order=0)

        response = fast_tenant_client.delete(
            reverse("paper-detail", kwargs={"pk": paper.pk})
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_valid_paper(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """Deletes paper"""
        paper = Paper.objects.create(name="Thesis", sort_order=0)
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.delete(
            reverse("paper-detail", kwargs={"pk": paper.pk})
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Paper.objects.filter(name="Thesis").count() == 0

    def test_only_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Non-staff users cannot delete"""
        paper = Paper.objects.create(name="Thesis", sort_order=0)
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.delete(
            reverse("paper-detail", kwargs={"pk": paper.pk})
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class CalculatePriceTestCase(FastTenantTestCase):
    """Tests for price calculation"""

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
        self.level = Level.objects.create(name="TestLevel")
        self.deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.DAY
        )
        self.paper = Paper.objects.create(name="TestPaper")
        self.writer_type = WriterType.objects.create(name="Premium")
        self.valid_payload = {
            "level": self.level.id,
            "deadline": self.deadline.id,
            "pages": 3,
            "writer_type": self.writer_type.id,
            "paper": self.paper.id,
        }
        self.user = User.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
        )

    def post(self, payload):
        """Method POST"""

        return self.client.post(
            reverse("calculator"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

    def test_valid_payload(self):
        """Confirm calculation for valid payload is correct"""
        service = Service.objects.create(
            level=self.level, deadline=self.deadline, paper=self.paper, amount=15.00
        )
        WriterTypeService.objects.create(
            writer_type=self.writer_type, service=service, amount=5.00
        )
        response = self.post(self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {
                "subtotal": "60.00",
                "total": "60.00",
                "coupon_code": None,
            },
        )

    def test_level_optional(self):
        """Ensure `level` is optional"""
        # A service with no level specified
        service = Service.objects.create(
            deadline=self.deadline, paper=self.paper, amount=15.00
        )
        WriterTypeService.objects.create(
            writer_type=self.writer_type, service=service, amount=5.00
        )
        payload = {**self.valid_payload, "level": ""}
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {
                "subtotal": "60.00",
                "total": "60.00",
                "coupon_code": None,
            },
        )

    def test_deadline_required(self):
        """Ensure `deadline` is provided in the request payload"""
        payload = {**self.valid_payload, "deadline": ""}
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pages_required(self):
        """Ensure `pages` is provided in the request payload"""
        payload = {**self.valid_payload, "pages": ""}
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_writer_type_optional(self):
        """Ensure `writer_type` can be optional"""
        Service.objects.create(
            level=self.level, deadline=self.deadline, paper=self.paper, amount=15.00
        )
        payload = {**self.valid_payload, "writer_type": ""}
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(
            response.data,
            {
                "subtotal": "45.00",
                "total": "45.00",
                "coupon_code": None,
            },
        )

    def test_service_priority(self):
        """Ensure a service with no level is given priority first"""
        Service.objects.create(
            level=self.level, deadline=self.deadline, paper=self.paper, amount=15.00
        )
        Service.objects.create(deadline=self.deadline, paper=self.paper, amount=12.00)
        payload = {**self.valid_payload, "writer_type": ""}
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {
                "subtotal": "36.00",
                "total": "36.00",
                "coupon_code": None,
            },
        )

    def test_writer_type_availability(self):
        """Ensure provided `writer_type` is available for service"""
        # Service exists but writer type price not set
        Service.objects.create(
            level=self.level, deadline=self.deadline, paper=self.paper, amount=15.00
        )
        response = self.post(self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_service_availability(self):
        """Ensure an appropriate message is returned if service does not exist"""
        # no service exists for posted deadline, level and paper
        response = self.post({**self.valid_payload, "writer_type": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # no service exists with posted deadline
        deadline = Deadline.objects.create(
            value=2, deadline_type=Deadline.DeadlineType.DAY
        )
        Service.objects.create(
            deadline=deadline, level=self.level, paper=self.paper, amount=15.00
        )
        response = self.post({**self.valid_payload, "writer_type": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # no service exists for posted level
        Service.objects.all().delete()
        level = Level.objects.create(name="High School")
        Service.objects.create(
            level=level, deadline=self.deadline, paper=self.paper, amount=15.00
        )
        response = self.post({**self.valid_payload, "writer_type": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # no service exists for posted paper
        Service.objects.all().delete()
        paper = Paper.objects.create(name="Admission Essay")
        Service.objects.create(
            paper=paper, level=self.level, deadline=self.deadline, amount=15.00
        )
        response = self.post({**self.valid_payload, "writer_type": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pages_min(self):
        """Ensure `pages` min value is 1"""
        Service.objects.create(
            level=self.level, deadline=self.deadline, paper=self.paper, amount=15.00
        )
        payload = {**self.valid_payload, "pages": 0, "writer_type": ""}
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        payload = {**self.valid_payload, "pages": 1, "writer_type": ""}
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_pages_max(self):
        """Ensure `pages` max value is 1000"""
        Service.objects.create(
            level=self.level, deadline=self.deadline, paper=self.paper, amount=15.00
        )
        payload = {**self.valid_payload, "pages": 1001, "writer_type": ""}
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        payload = {**self.valid_payload, "pages": 1000, "writer_type": ""}
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_discount_anonymous_user(self):
        """Ensure correct discount is given if user is anonymous"""
        Service.objects.create(
            deadline=self.deadline, level=self.level, paper=self.paper, amount=15
        )
        start_date = timezone.now()
        end_date = start_date + timedelta(days=1)

        # First Timer coupon
        Coupon.objects.create(
            code="MCEFirst",
            percent_off=20,
            start_date=start_date,
            end_date=end_date,
            coupon_type=Coupon.CouponType.FIRST_TIMER,
        )
        # Regular coupon
        Coupon.objects.create(
            code="MCE20",
            percent_off=10,
            minimum=20.00,
            start_date=start_date,
            end_date=end_date,
        )
        response = self.post({**self.valid_payload, "writer_type": ""})
        self.assertEqual(
            response.data,
            {
                "subtotal": "45.00",
                "total": "36.00",
                "coupon_code": "MCEFirst",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_discount_authenticated_user(self):
        """Ensure correct discount if user is authenticated"""
        service = Service.objects.create(
            deadline=self.deadline, level=self.level, paper=self.paper, amount=15
        )
        start_date = timezone.now()
        end_date = start_date + timedelta(days=1)

        # First Timer coupon
        Coupon.objects.create(
            code="MCEFirst",
            percent_off=20,
            start_date=start_date,
            end_date=end_date,
            coupon_type=Coupon.CouponType.FIRST_TIMER,
        )
        # Regular coupon
        min_price_coupon = Coupon.objects.create(
            code="MCE20",
            percent_off=10,
            minimum=20.00,
            start_date=start_date,
            end_date=end_date,
        )

        # First timer coupon is applied if user is first timer
        payload = {**self.valid_payload, "writer_type": ""}
        self.client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(self.user).access_token}
        )
        response = self.client.post(
            reverse("calculator"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        self.assertEqual(
            response.data,
            {
                "subtotal": "45.00",
                "total": "36.00",
                "coupon_code": "MCEFirst",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Test if user is not first timer
        #  Min price coupon is applied if user is not first timer
        Order.objects.create(owner=self.user, status=Order.Status.PAID)
        response = self.client.post(
            reverse("calculator"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        self.assertEqual(
            response.data,
            {
                "subtotal": "45.00",
                "total": "40.50",
                "coupon_code": "MCE20",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Min coupon is applied if amount payable is exactly equal to coupon min amount
        min_price_coupon.minimum = 45.00
        min_price_coupon.save()
        min_price_coupon.refresh_from_db()
        self.assertEqual(
            min_price_coupon.minimum, service.amount * self.valid_payload["pages"]
        )
        response = self.client.post(
            reverse("calculator"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        self.assertEqual(
            response.data,
            {
                "subtotal": "45.00",
                "total": "40.50",
                "coupon_code": "MCE20",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Min coupon is not applied if amount payable is less than coupon min amount
        min_price_coupon.minimum = 46.00
        min_price_coupon.save()
        min_price_coupon.refresh_from_db()
        self.assertGreater(
            min_price_coupon.minimum, service.amount * self.valid_payload["pages"]
        )
        response = self.client.post(
            reverse("calculator"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        self.assertEqual(
            response.data,
            {
                "subtotal": "45.00",
                "total": "45.00",
                "coupon_code": None,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # The first coupon with the largest minimum value is applied if coupons multiple
        Coupon.objects.create(
            code="MCE5",
            percent_off=5,
            minimum=30.00,
            start_date=start_date,
            end_date=end_date,
        )
        response = self.client.post(
            reverse("calculator"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        self.assertEqual(
            response.data,
            {
                "subtotal": "45.00",
                "total": "42.75",
                "coupon_code": "MCE5",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_discount_coupon_expiry(self):
        """Ensure discount is not applied if coupon expired"""
        Service.objects.create(
            deadline=self.deadline, level=self.level, paper=self.paper, amount=15
        )

        # Ensure first timer expired coupon is not applied
        Coupon.objects.create(
            code="MCEFirst",
            percent_off=20,
            start_date=timezone.now() - timedelta(days=3),
            end_date=timezone.now() - timedelta(days=1),
            coupon_type=Coupon.CouponType.FIRST_TIMER,
        )
        response = self.post({**self.valid_payload, "writer_type": ""})
        self.assertEqual(
            response.data,
            {
                "subtotal": "45.00",
                "total": "45.00",
                "coupon_code": None,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Ensure min price expired coupon is not applied for non first timer
        Order.objects.create(owner=self.user, status=Order.Status.PAID)
        Coupon.objects.create(
            code="Expired",
            percent_off=10,
            minimum=20.00,
            start_date=timezone.now() - timedelta(days=3),
            end_date=timezone.now() - timedelta(days=1),
        )
        response = self.post({**self.valid_payload, "writer_type": ""})
        self.assertEqual(
            response.data,
            {
                "subtotal": "45.00",
                "total": "45.00",
                "coupon_code": None,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class WriterTypeServiceTestCase(FastTenantTestCase):
    """Tests for GET writer type service"""

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
        level = Level.objects.create(name="TestLevel")
        deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.DAY
        )
        paper = Paper.objects.create(name="TestPaper")
        self.service = Service.objects.create(
            level=level, deadline=deadline, paper=paper, amount=15.00
        )
        self.writer_type_1 = WriterType.objects.create(
            name="Top", sort_order=1, description="Awesome description"
        )
        self.writer_type_2 = WriterType.objects.create(name="Premium", sort_order=2)
        WriterTypeService.objects.create(
            writer_type=self.writer_type_1, service=self.service, amount=5.00
        )
        WriterTypeService.objects.create(
            writer_type=self.writer_type_2, service=self.service, amount=8.00
        )
        tag_1 = WriterTypeTag.objects.create(title="Popular")
        self.writer_type_1.tags.add(tag_1)

        self.valid_payload = {
            "level": level.pk,
            "deadline": deadline.pk,
            "paper": paper.pk,
        }
        self.maxDiff = None

    def post(self, payload):
        """Method POST"""
        return self.client.post(
            reverse("writer_type"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

    def test_valid_payload(self):
        """Ensure returns writer types for valid payload"""
        response = self.post(self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            json.dumps(response.data, cls=DjangoJSONEncoder),
            json.dumps(
                [
                    {
                        "writer_type": {
                            "id": str(self.writer_type_1.pk),
                            "name": self.writer_type_1.name,
                            "description": self.writer_type_1.description,
                            "tags": ["Popular"],
                        },
                        "amount": "5.00",
                    },
                    {
                        "writer_type": {
                            "id": str(self.writer_type_2.pk),
                            "name": self.writer_type_2.name,
                            "description": self.writer_type_2.description,
                            "tags": [],
                        },
                        "amount": "8.00",
                    },
                ],
                cls=DjangoJSONEncoder,
            ),
        )

    def test_no_writer_types(self):
        """Ensure the response is correct if no writer types available"""
        level = Level.objects.create(name="High School")
        deadline = Deadline.objects.create(
            value=2, deadline_type=Deadline.DeadlineType.DAY
        )
        paper = Paper.objects.create(name="Argumentative Essay")
        response = self.post(
            {"level": level.pk, "deadline": deadline.pk, "paper": paper.pk}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_invalid_level(self):
        """Ensure a validation error is raised if level invalid"""
        response = self.post({**self.valid_payload, "level": "871"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_deadline(self):
        """Ensure a validation error is raised if deadline invalid"""
        response = self.post({**self.valid_payload, "deadline": "871"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_paper(self):
        """Ensure a validation error is raised if paper invalid"""
        response = self.post({**self.valid_payload, "paper": "871"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_level_optional(self):
        """Ensure level is optional"""
        response = self.post({**self.valid_payload, "level": ""})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_deadline_required(self):
        """Ensure deadline is required"""
        response = self.post({**self.valid_payload, "deadline": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_paper_required(self):
        """Ensure paper is required"""
        response = self.post({**self.valid_payload, "paper": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@pytest.mark.django_db
class TestCreatePrices:
    """Tests for create prices"""

    @pytest.fixture()
    def set_up(self):
        paper_1 = Paper.objects.create(name="Case Study")
        level_1 = Level.objects.create(name="High School")
        level_2 = Level.objects.create(name="College")
        deadline_1 = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.DAY
        )
        deadline_2 = Deadline.objects.create(
            value=2, deadline_type=Deadline.DeadlineType.DAY
        )
        deadline_3 = Deadline.objects.create(
            value=3, deadline_type=Deadline.DeadlineType.DAY
        )
        deadline_4 = Deadline.objects.create(
            value=4, deadline_type=Deadline.DeadlineType.DAY
        )

        return locals()

    def test_auth_required(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        response = fast_tenant_client.post(reverse("service-create-bulk"), data={})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_only_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Non-staff is not allowed to create prices"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.post(reverse("service-create-bulk"), data={})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        set_up,
        create_active_subscription,
    ):
        """Staff can create prices"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        paper_1 = set_up["paper_1"]
        level_1 = set_up["level_1"]
        deadline_1 = set_up["deadline_1"]
        deadline_2 = set_up["deadline_2"]
        deadline_3 = set_up["deadline_3"]
        valid_payload = {
            "paper_id": str(paper_1.id),
            "prices": [
                {
                    "deadline_id": str(deadline_1.id),
                    "level_id": str(level_1.id),
                    "amount": 10.56,
                },
                {
                    "deadline_id": str(deadline_2.id),
                    "level_id": str(level_1.id),
                    "amount": 9.15,
                },
                {
                    "deadline_id": str(deadline_3.id),
                    "level_id": str(level_1.id),
                    "amount": 8.00,
                },
            ],
        }
        response = fast_tenant_client.post(
            reverse("service-create-bulk"),
            data=json.dumps(valid_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Service.objects.filter(paper__id=paper_1.id).count() == 3

    def test_level_optional(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        set_up,
        create_active_subscription,
    ):
        """Level is optional"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        paper_1 = set_up["paper_1"]
        deadline_1 = set_up["deadline_1"]
        deadline_2 = set_up["deadline_2"]
        deadline_3 = set_up["deadline_3"]
        valid_payload = {
            "paper_id": str(paper_1.id),
            "prices": [
                {
                    "deadline_id": str(deadline_1.id),
                    "level_id": None,
                    "amount": 10.56,
                },
                {
                    "deadline_id": str(deadline_2.id),
                    "level_id": None,
                    "amount": 9.15,
                },
                {
                    "deadline_id": str(deadline_3.id),
                    "level_id": None,
                    "amount": 8.00,
                },
            ],
        }
        response = fast_tenant_client.post(
            reverse("service-create-bulk"),
            data=json.dumps(valid_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Service.objects.filter(paper__id=paper_1.id).count() == 3

    def discards_existing_records(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        set_up,
        create_active_subscription,
    ):
        """Any existing records are discarded"""
        paper_1 = set_up["paper_1"]
        level_1 = set_up["level_1"]
        level_2 = set_up["level_2"]
        deadline_1 = set_up["deadline_1"]
        deadline_2 = set_up["deadline_2"]
        deadline_3 = set_up["deadline_3"]
        deadline_4 = set_up["deadline_4"]

        Service.objects.create(
            level=level_1, paper=paper_1, deadline=deadline_1, amount=1
        )
        Service.objects.create(
            level=level_1, paper=paper_1, deadline=deadline_2, amount=1
        )
        Service.objects.create(
            level=level_1, paper=paper_1, deadline=deadline_3, amount=1
        )
        Service.objects.create(
            level=level_2, paper=paper_1, deadline=deadline_4, amount=1
        )

        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )

        valid_payload = {
            "paper_id": str(paper_1.id),
            "prices": [
                {
                    "deadline_id": str(deadline_1.id),
                    "level_id": str(level_1.id),
                    "amount": 10.56,
                },
                {
                    "deadline_id": str(deadline_2.id),
                    "level_id": str(level_1.id),
                    "amount": 9.15,
                },
                {
                    "deadline_id": str(deadline_3.id),
                    "level_id": str(level_1.id),
                    "amount": 8.00,
                },
            ],
        }
        response = fast_tenant_client.post(
            reverse("service-create-bulk"),
            data=json.dumps(valid_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Service.objects.filter(paper__id=paper_1.id).count() == 3
        assert (
            Service.get(level=level_1, paper=paper_1, deadline=deadline_1).amount
            == 10.56
        )
        assert (
            Service.get(level=level_1, paper=paper_1, deadline=deadline_2).amount
            == 9.15
        )
        assert (
            Service.get(level=level_1, paper=paper_1, deadline=deadline_3).amount
            == 8.00
        )

    def test_paper_id_required(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        set_up,
        create_active_subscription,
    ):
        """paper_id is required"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        level_1 = set_up["level_1"]
        deadline_1 = set_up["deadline_1"]
        deadline_2 = set_up["deadline_2"]
        deadline_3 = set_up["deadline_3"]
        response = fast_tenant_client.post(
            reverse("service-create-bulk"),
            data=json.dumps(
                {
                    "prices": [
                        {
                            "deadline_id": deadline_1.id,
                            "level_id": level_1.id,
                            "amount": 10.56,
                        },
                        {
                            "deadline_id": deadline_2.id,
                            "level_id": level_1.id,
                            "amount": 9.15,
                        },
                        {
                            "deadline_id": deadline_3.id,
                            "level_id": level_1.id,
                            "amount": 8.00,
                        },
                    ],
                },
                cls=DjangoJSONEncoder,
            ),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response = fast_tenant_client.post(
            reverse("service-create-bulk"),
            data=json.dumps(
                {
                    "paper_id": "",
                    "prices": [
                        {
                            "deadline_id": deadline_1.id,
                            "level_id": level_1.id,
                            "amount": 10.56,
                        },
                        {
                            "deadline_id": deadline_2.id,
                            "level_id": level_1.id,
                            "amount": 9.15,
                        },
                        {
                            "deadline_id": deadline_3.id,
                            "level_id": level_1.id,
                            "amount": 8.00,
                        },
                    ],
                },
                cls=DjangoJSONEncoder,
            ),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestDeletePrices:
    """Tests for delete prices"""

    @pytest.fixture()
    def set_up(self):
        paper_1 = Paper.objects.create(name="Case Study")
        level_1 = Level.objects.create(name="High School")
        deadline_1 = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.DAY
        )
        deadline_2 = Deadline.objects.create(
            value=2, deadline_type=Deadline.DeadlineType.DAY
        )
        deadline_3 = Deadline.objects.create(
            value=3, deadline_type=Deadline.DeadlineType.DAY
        )

        Service.objects.create(
            level=level_1, paper=paper_1, deadline=deadline_1, amount=1
        )
        Service.objects.create(
            level=level_1, paper=paper_1, deadline=deadline_2, amount=1
        )
        Service.objects.create(
            level=level_1, paper=paper_1, deadline=deadline_3, amount=1
        )

        return locals()

    def test_auth_required(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        response = fast_tenant_client.post(reverse("service-delete-bulk"), data={})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_only_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Non-staff is not allowed to create prices"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.post(reverse("service-delete-bulk"), data={})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        set_up,
        create_active_subscription,
    ):
        """Staff can delete prices"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        paper_1 = set_up["paper_1"]

        response = fast_tenant_client.post(
            reverse("service-delete-bulk"),
            data={"paper_id": paper_1.id},
        )
        assert response.status_code == status.HTTP_200_OK
        assert Service.objects.filter(paper__id=paper_1.id).count() == 0

    def test_paper_id_required(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        set_up,
        create_active_subscription,
    ):
        """paper_id is required"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.post(
            reverse("service-delete-bulk"),
            data={},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response = fast_tenant_client.post(
            reverse("service-delete-bulk"),
            data={"paper_id": ""},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
