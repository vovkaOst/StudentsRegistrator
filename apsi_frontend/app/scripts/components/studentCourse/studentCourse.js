/**
 * Created by marzuz on 27.12.16.
 */
'use strict';

angular.module('apsiFrontendApp')
	.controller('StudentCourseCtrl', function($scope, $state, coursename, Restangular) {
    $scope.week = [
      {
        id: 0,
        name: 'Poniedziałek'
      },
      {
        id: 1,
        name: 'Wtorek'
      },
      {
        id: 2,
        name: 'Środa'
      },
      {
        id: 3,
        name: 'Czwartek'
      },
      {
        id: 4,
        name: 'Piątek'
      }
    ];

    function findDay(day_id) {
        for (var i=0; i<$scope.week.length; i++) {
          if($scope.week[i].id === day_id){
            return $scope.week[i].name;
          }
        }
    }

    function dayFormat(termines) {
        for (var i=0; i<termines.length; i++) {
          termines[i].day = findDay(termines[i].day)
        }
        return termines;
    }

    Restangular.oneUrl('courses', 'http://localhost:8000/me/').get().then(function(me) {
        $scope.me = me;
        Restangular.oneUrl('courses', 'http://localhost:8000/courses/'+coursename+'/class_types/').get()
          .then(function(classType) {
            console.log('types: '+classType);
            $scope.classType = classType;
            for (var i=0; i < classType.length; i++) {
              $scope.classType[i].time_slots = dayFormat($scope.classType[i].time_slots);
              if($scope.classType[i].group_open == true) {
                $scope.classType[i].group_open = 'Dozwolone.';
              } else {
                $scope.classType[i].group_open = 'Zabronione.'
              }

            }
        });
    });



    function findBySpecField(data, value) {
      var container = data;
      for (var i = 0; i < container.length; i++) {
          // console.log('    '+container[i].id);
            if (container[i].id === value) {
                // console.log('+++'+container[i].full_name);
              return(container[i]);
            }
      }
      return '';
    }

	  Restangular.oneUrl('courses', 'http://localhost:8000/courses/'+coursename+'/').get()  // GET: /courses/{name}
			.then(function(course) {
			  $scope.courseDesc = course;
        $scope.courseData = $scope.courseDesc;
        Restangular.oneUrl('coursesdd', 'http://localhost:8000/tutors/').get()  // GET: /courses/{name}
          .then(function(tutors) {
            $scope.courseDescSelectedTutor = findBySpecField(tutors, $scope.courseData.tutor);
            console.log('Tutor: ' + $scope.courseDescSelectedTutor.id);
          });
	 	});



    $scope.sign = function (type, termine) {
      Restangular.oneUrl('asdda','http://localhost:8000/courses/'+coursename+'/class_types/'+type+'/time_slots/'+termine+'/registration/').put().then(
            function(data)
            {
              console.log(data);
              if (data != undefined) {
                if (data.detail != undefined) {
                  console.log(data.detail);
                  alert(data.detail)
                }
              }
              console.log('registered:  ' +type+termine);
              $state.reload();
            },
            function(error)
            {
              if (error.data != undefined) {
                if (error.data.detail != undefined) {
                  console.log(error.data.detail);
                  alert(error.data.detail)
                }
              } else {
                alert('Zapis nieudany. Przekroczona maksymalną liczbę studentów lub zapisy są już zamnknięte.');
              }
              console.log('Cannot register. ');
            }
        );
    };

    $scope.manageGropus = function (typeId) {
      $state.go('groupsManager',{courseid: coursename, classid:typeId});
    };

    $scope.goBack = function() {
      $state.go('studentCourses');
    };


	});
