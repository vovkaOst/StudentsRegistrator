from django.http.response import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, GenericViewSet
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from rest_framework.decorators import detail_route, list_route
from rest_framework.exceptions import PermissionDenied
from rest_framework.mixins import ListModelMixin
from rest_framework.exceptions import APIException
from django.core.exceptions import ValidationError
from courses.exceptions import RegistrationClosedError
from courses.exceptions import GroupRegistrationClosedError
from courses.exceptions import MaxNumberRegisteredError
from courses.serializers import (
    ClassTypeSerializer,
    CourseSerializer,
    GroupSerializer,
    RegisteredStudentsSerializer,
    TimeSlotSerializer,
)
from courses.models import (
    ClassType,
    Course,
    Group,
    TimeSlot,
)
from users.serializers import UserSerializer
from users.models import User


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

class RestrictedStudentPermissions(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_student()

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

    PATHS:
    /clear_all_data - removes all groups and student lists of the course (tutor only)
    /class_types - list of class types available
    /registration - registration for a course (students only)
    /registeres_students - list of a students registered for a course 
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

    @detail_route(['PUT'])
    def clear_all_data(self, request, pk):

        """ Removes all groups and student lists of the subject.
            Leaves all time slots and course types untoched, coz they're usually stable from year to year. 
            Can be used only after course registration is closed.
        """

        course = self.get_object()
        #user = request.user
        if course.state == Course.State.REGISTRATION_OPENED:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={'detail': 'Course must have close registration if you want to remove all students data'}
            )
        
        for cl in ClassType.objects.filter(course_id=course):
            Group.objects.filter(class_type=cl).delete()

        for user in course.registered_students.all():
            course.registered_students.remove(user)
        
        return Response(status=status.HTTP_204_NO_CONTENT)

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
            for group in Group.objects.filter(class_type__course=course, student_members=user):
                if group.creator == user:
                    if group.student_members.count() > 1:
                        return Response(
                            status=status.HTTP_400_BAD_REQUEST,
                            data={
                                'detail': 'W stworzonej przez ciebie groupupie są inni studenci. Nie może się wyrejestrować z przedmiotu.'}
                        )
                    else:
                        group.delete()
                else:
                    group.student_members.remove(user)
            
            for time_slot in TimeSlot.objects.filter(class_type__course=course, enrolled_students=user):
                time_slot.enrolled_students.remove(user)
            course.registered_students.remove(user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RegisteredStudentsViewSet(ListModelMixin, GenericViewSet):
    serializer_class = UserSerializer

    def get_queryset(self):
        return User.objects.filter(courses_attended=self.kwargs['course_pk'])

    def update(self, request, *args, **kwargs):
        student = User.objects.get(pk=kwargs['pk'])
        student.courses_attended.add(self.kwargs['course_pk'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    def destroy(self, request, *args, **kwargs):
        student = self.get_object()
        course = Course.objects.get(pk=kwargs['course_pk'])
        for group in Group.objects.filter(class_type__course=course, student_members=student):
            if group.creator == student:
                group.delete()
            else:
                group.student_members.remove(student)

        for time_slot in TimeSlot.objects.filter(class_type__course=course, enrolled_students=student):
            time_slot.enrolled_students.remove(student)
        student.courses_attended.remove(self.kwargs['course_pk'])
        return Response(status=status.HTTP_204_NO_CONTENT)


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
        if user.is_student() is not True:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={'detail': 'user should be student'}
            )

        if time_slot.class_type.time_slots_state == ClassType.TimeSlotsState.TIMESLOTS_REGISTRATION_CLOSED:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={'detail': 'Prowadzący zaakceptował terminy. Nie możesz ich zmienić'}
            )
            
        if request.method == 'PUT':
            collision_time_slots = TimeSlot.objects.filter(enrolled_students = user).exclude(class_type=time_slot.class_type)
            collided = list()
            #courseName = time_slot.class_type.course.name
            for ts in collision_time_slots:
                if (ts.time_start>=time_slot.time_start and ts.time_start<time_slot.time_end) or (ts.time_end>time_slot.time_start and ts.time_end<=time_slot.time_end):
                    collided.append((ts.class_type.name, ts.time_start, ts.time_end))
            previous_user_slot = TimeSlot.objects.filter(class_type=time_slot.class_type, enrolled_students = user)
            if time_slot.enrolled_students.count() >= time_slot.max_students_enrolled:
                raise MaxNumberRegisteredError()
            if previous_user_slot:
                previous_user_slot.first().enrolled_students.remove(user)
            time_slot.enrolled_students.add(user)
            if collided:
                strRepresent = "Masz kolizje terminów przy zapisie na ten termin:\n"
                for t in collided:
                    strRepresent += t[0] + "\n  - od " + str(t[1]) + "  do " + str(t[2]) +"\n"
                return Response(
                    status=status.HTTP_202_ACCEPTED,
                    data={'detail': strRepresent}
                )

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
    
    @list_route(['PUT'], permission_classes=[TutorsOnlyPermissions])
    def open(self, request, course_pk, class_type_pk):
        class_type = (
            ClassType.objects
            .filter(
                pk=class_type_pk,
                time_slots_state=ClassType.TimeSlotsState.TIMESLOTS_REGISTRATION_CLOSED
            )
            .first()
        )

        if not class_type:
            raise Http404

        class_type.time_slots_state = ClassType.TimeSlotsState.TIMESLOTS_REGISTRATION_OPEN
        class_type.save()
        return Response({})

    @list_route(['PUT'], permission_classes=[TutorsOnlyPermissions])
    def close(self, request, course_pk, class_type_pk):
        class_type = (
            ClassType.objects
            .filter(
                pk=class_type_pk,
                time_slots_state=ClassType.TimeSlotsState.TIMESLOTS_REGISTRATION_OPEN
            )
            .first()
        )
        
        if not class_type:
            raise Http404

        class_type.time_slots_state = ClassType.TimeSlotsState.TIMESLOTS_REGISTRATION_CLOSED
        class_type.save()
        return Response({})


class GroupsViewSet(ModelViewSet):
    serializer_class = GroupSerializer
    permission_classes = (RestrictedStudentPermissions,)
    model = Group

    def get_queryset(self):
        return Group.objects.filter(class_type_id=self.kwargs['class_type_pk'])

    def perform_create(self, serializer):
        class_type = ClassType.objects.filter(
            pk=self.kwargs['class_type_pk'],
            groups_state=ClassType.GroupsState.GROUPS_REGISTRATION_OPEN,
        )

        if not class_type:
            raise Http404

        groups = (
            self.request.user.attended_groups
            .filter(
                class_type_id=self.kwargs['class_type_pk']
            )
        )
        if groups.exists():
            for group in groups:
                group.student_members.remove(self.request.user)

        serializer.save(
            class_type_id=self.kwargs['class_type_pk'],
            creator=self.request.user,
            student_members=[self.request.user]
        )

    def perform_destroy(self, instance):
        if instance.creator != self.request.user:
            raise Http404
        if instance.class_type.groups_state == ClassType.GroupsState.GROUPS_REGISTRATION_CLOSED:
            raise GroupRegistrationClosedError()
        instance.delete()

    @detail_route(['PUT'], permission_classes=[StudentsOnlyPermissions])
    def register(self, request, course_pk, class_type_pk, pk):
        course = Course.objects.filter(pk=course_pk).first()
        if not course:
            raise Http404

        if not course.state == Course.State.REGISTRATION_OPENED:
            raise RegistrationClosedError()

        group = self.get_object()

        if group.student_members.count() >= group.class_type.max_students_in_group:
            raise MaxNumberRegisteredError()

        groups = (
            request.user.attended_groups
            .filter(
                class_type_id=self.kwargs['class_type_pk']
            )
        )
        if groups.exists():
            for old_group in groups:
                old_group.student_members.remove(self.request.user)

        group.student_members.add(request.user)
        return Response({})

    @detail_route(['POST'], permission_classes=[TutorsOnlyPermissions])
    def move_student(self, request, course_pk, class_type_pk, pk):
        course = Course.objects.get(pk=course_pk)
        if not course:
            raise Http404

        student_id = int(request.data.get('student_id'))
        user = User.objects.get(pk=student_id)
        if not user:
            raise Http404

        group = self.get_object()

        groups = (
            user.attended_groups
            .filter(
                class_type_id=self.kwargs['class_type_pk']
            )
        )
        if groups.exists():
            for old_group in groups:
                old_group.student_members.remove(user)

        group.student_members.add(user)
        return Response({})

    @list_route(['PUT'], permission_classes=[TutorsOnlyPermissions])
    def open(self, request, course_pk, class_type_pk):
        class_type = (
            ClassType.objects
            .filter(
                pk=class_type_pk,
                groups_state=ClassType.GroupsState.GROUPS_REGISTRATION_CLOSED
            )
            .first()
        )

        if not class_type:
            raise Http404

        class_type.groups_state = ClassType.GroupsState.GROUPS_REGISTRATION_OPEN
        class_type.save()

        return Response({})

    @list_route(['PUT'], permission_classes=[TutorsOnlyPermissions])
    def close(self, request, course_pk, class_type_pk):
        class_type = (
            ClassType.objects
            .filter(
                pk=class_type_pk,
                groups_state=ClassType.GroupsState.GROUPS_REGISTRATION_OPEN
            )
            .first()
        )

        if not class_type:
            raise Http404

        class_type.groups_state = (
            ClassType.GroupsState.GROUPS_REGISTRATION_CLOSED
        )
        class_type.save()

        return Response({})
