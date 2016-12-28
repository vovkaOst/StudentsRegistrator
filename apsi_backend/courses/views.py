from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from rest_framework.decorators import detail_route
from rest_framework.exceptions import PermissionDenied

from courses.serializers import CourseSerializer, RegisteredStudentsSerializer, ClassTypeSerializer, TimeSlotSerializer
from courses.models import Course, ClassType, TimeSlot
from users.serializers import UserSerializer


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

class RestrictedPermissions(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_tutor()

class StudentsOnlyPermissions(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.user.is_student()

class TutorsOnlyPermissions(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.user.is_tutor()


class CourseViewSet(ModelViewSet):

    """ 
    Course resource. 
    
    For the state argument you should pass 0 or one, meaning:
    
    REGISTRATION_OPENED = 0
    STUDENTS_LIST_ACCEPTED = 1
    """

    serializer_class = CourseSerializer
    permission_classes = (CoursesPermissions,)

    def get_queryset(self):

        """ Returns list of objects. """

        registered = self.request.query_params.get('registered', None)
        if registered == 'true':
            return self.request.user.courses_attended
        if registered == 'false':
            return Course.objects.exclude(registered_students__pk=self.request.user.pk)

        tutored = self.request.query_params.get('tutored', None)
        if tutored == 'true':
            return self.request.user.courses_taught
        if tutored == 'false':
            return Course.objects.exclude(tutor__pk=self.request.user.pk)
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

        """ Registers actually logged student (or that who actually sent request) to current course. """

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

    @detail_route(['GET', 'POST', 'DELETE'])
    def registered_students(self, request, pk):

        """ Shows the list of students registered for that course (can be only seen by tutor). """

        course = self.get_object()
        if request.method == 'GET':
            response_serializer = UserSerializer(course.registered_students.all(), many=True)
            return Response(response_serializer.data)

        students_serializer = RegisteredStudentsSerializer(data=request.data)
        students_serializer.is_valid(raise_exception=True)
        students = students_serializer.validated_data['students']

        if request.method == 'POST':
            course.registered_students.add(*students)
        if request.method == 'DELETE':
            course.registered_students.remove(*students)

        course = self.get_object()
        response_serializer = UserSerializer(course.registered_students.all(), many=True)
        return Response(response_serializer.data)


class ClassTypeViewSet(ModelViewSet):

    """
    Class type of the course.

    For example it can be project, training, laboratorium or other defined by tutor.

    name parameter is a string description of a course type 
    """ 

    serializer_class = ClassTypeSerializer
    permission_classes = (RestrictedPermissions,)
    
    def get_queryset(self):
        return ClassType.objects.filter(course_id=self.kwargs['course_pk'])

    def perform_create(self, serializer):
        serializer.save(course_id=self.kwargs['course_pk'])


class TimeSlotViewSet(ModelViewSet):

    """
    Time slot of the course.

    ***
    Field Name | Field formats
    ---------- | -------------
    day        | {0,1,2,3,4}
    time_start | 'hh:mm:ss'
    time_end   | 'hh:mm:ss'


    day field values meaning:
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4

    Example json value as an argument:
    ```json
    {
    "id": 7,
    "day": 2,
    "time_start": "18:15:00",
    "time_end": "20:00:00"
    },
    ``` 

    """ 
    serializer_class = TimeSlotSerializer
    permission_classes = (RestrictedPermissions,)
    model = TimeSlot

    def get_queryset(self):
        return TimeSlot.objects.filter(class_type_id=self.kwargs['class_type_pk'])

    def perform_create(self, serializer):
        serializer.save(class_type_id=self.kwargs['class_type_pk'])

    @detail_route(['PUT', 'DELETE'], permission_classes=[StudentsOnlyPermissions])
    def registration(self, request, course_pk, class_type_pk, pk):
        time_slot = self.get_object()
        user = request.user
        if user.is_student()!=True:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={'detail': 'user should be student'}
            )
        if request.method == 'PUT':
            previous_user_slot = TimeSlot.objects.filter(class_type=time_slot.class_type, enrolled_students = user)
            print(previous_user_slot)
            if previous_user_slot:
                previous_user_slot.first().enrolled_students.remove(user)
            time_slot.enrolled_students.add(user)
        if request.method == 'DELETE':
            time_slot.enrolled_students.remove(user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @detail_route(['GET', 'POST', 'DELETE'])
    def enrolled_students(self, request, course_pk, class_type_pk, pk):
        time_slot = self.get_object()
        if request.method == 'GET':
            response_serializer = UserSerializer(time_slot.enrolled_students.all(), many=True)
            return Response(response_serializer.data)

        students_serializer = RegisteredStudentsSerializer(data=request.data)
        students_serializer.is_valid(raise_exception=True)
        students = students_serializer.validated_data['students']

        if request.method == 'POST':
            time_slot.enrolled_students.add(*students)
        if request.method == 'DELETE':
            time_slot.enrolled_students.remove(*students)

        time_slot = self.get_object()
        response_serializer = UserSerializer(time_slot.enrolled_students.all(), many=True)
        return Response(response_serializer.data)