from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from rest_framework.decorators import detail_route
from rest_framework.exceptions import PermissionDenied

from courses.serializers import CourseSerializer
from courses.models import Course


class CoursesPermissions(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_tutor()

    def has_object_permission(self, request, view, obj):
        if request.method not in SAFE_METHODS + ('post',):
            return obj.tutor == request.user
        return True


class StudentsOnlyPermissions(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.user.is_student()


class CourseViewSet(ModelViewSet):
    serializer_class = CourseSerializer
    permission_classes = (CoursesPermissions,)

    def get_queryset(self):
        registered = self.request.query_params.get('registered', None)
        if registered is not None:
            return self.request.user.courses_attended
        tutored = self.request.query_params.get('tutored', None)
        if tutored is not None:
            return self.request.user.courses_taught
        return Course.objects.prefetch_related('registered_students').all()

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # refresh the instance from the database.
            try:
                instance = self.get_object()
            except PermissionDenied:
                pass  # ignore permission denied exception at this point
            serializer = self.get_serializer(instance)

        return Response(serializer.data)

    @detail_route(['PUT', 'DELETE'], permission_classes=[StudentsOnlyPermissions])
    def registration(self, request, pk):
        course = self.get_object()
        user = request.user
        if user.is_student() and course.state != Course.State.REGISTRATION_OPENED:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={'detail': 'Course must have an open registration'}
            )
        if request.method == 'PUT':
            course.registered_students.add(user)
        if request.method == 'DELETE':
            course.registered_students.remove(user)
        return Response(status=status.HTTP_204_NO_CONTENT)
