/**
 * Created by marzuz on 29.12.16.
 */
'use strict';

angular.module('apsiFrontendApp')
	.controller('GroupsManagerCtrl', function($scope, $state, courseCode, typeId, Restangular) {
    console.log("asfd");
    $scope.courseCode = courseCode;
    $scope.newGroupVisible = 'hidden';
    $scope.groupName = null;
    $scope.studentID = null;
    $scope.newGroupID = null;
    console.log("asfd");
    Restangular.oneUrl('coursesdd', 'http://localhost:8000/me/').get()  // Pobierz MNIE (usera)
      .then(function(me) {
        $scope.meMe = me;
      });

    Restangular.oneUrl('courses', 'http://localhost:8000/courses/'+courseCode+'/class_types/'+typeId+'/groups/').get()  // Dawaj Grupy dla zajec
			.then(function(classGroups) {
			  $scope.classGroups = classGroups;
        $scope.isMyGroup = false;
        console.log($scope.classGroups);
          Restangular.oneUrl('coursesdd', 'http://localhost:8000/me/').get()  // Pobierz MNIE (usera)
            .then(function(me) {
              $scope.me = me;
              if (me.type = 1) {
                $scope.isTutor = true;
              }
              console.log("asfd");
              for (var i = 0; i < $scope.classGroups.length; i++) {
                console.log("asfd");
                console.log($scope.classGroups[i].creator.id);
                if ($scope.classGroups[i].creator.id === me.id) {
                  console.log("Znaleziony");
                  $scope.isMyGroup = true;
                  $scope.myGroup = $scope.classGroups[i];
                  break;
                }
              }
          });
	 	});

    $scope.createGroup = function () {
      $scope.newGroupVisible = 'visible';
    };

    $scope.acceptGroup = function(groupId) {
 	    Restangular.oneUrl('acceptGroup', 'http://localhost:8000/courses/'+courseCode+'/class_types/'+typeId+'/groups/'+groupId+'/close').put().then(
          function() {
              console.log('Accepted group');
              $state.reload();
          },
          function() {
              console.log('Cannot accept group');
          }
        );
    };

    $scope.submitGroup = function (name) {
      console.log(name);
      var newGroup = {
        name: name
      };
      Restangular.oneUrl('asd','http://localhost:8000/courses/'+courseCode+'/class_types/'+typeId+'/').post('groups/',newGroup).then(
        function() {
          console.log('Created new Group.  ');
          $scope.newGroupVisible = 'hidden';
          $state.reload();
        },
        function()
        {
          console.log('Cannot create Group.');
        }
      );
    };

    $scope.moveStudent = function(studentId, newGroupId) {
      var data = {
        'new_group_id': newGroupId,
        'student_id': studentId
      };
      Restangular.oneUrl('moveStudent', 'http://localhost:8000/courses/'+courseCode+'/class_types/'+typeId+'/groups/move').put(data)
        .then(function() {
          console.log(groupId+' register');
          $state.reload();
      });
    };

    $scope.signToGroup = function (groupId) {
      Restangular.oneUrl('courses', 'http://localhost:8000/courses/'+courseCode+'/class_types/'+typeId+'/groups/'+groupId+'/register/').put()
        .then(function() {
          console.log(groupId+' register');
          $state.reload();
      });
    };

    $scope.removeGroup = function () {
      Restangular.oneUrl('courses', 'http://localhost:8000/courses/'+courseCode+'/class_types/'+typeId+'/groups/'+$scope.myGroup.id+'/').remove().then(
          function()
          {
            console.log('Group deleted');
            $state.reload();
          },
          function ()
          {
            console.log('remove fail.');
          }
      );
    };

    $scope.goBack = function () {
      if ($scope.meMe.type == 1){
        $state.go('courseedit', {courseid: courseCode});
      } else {
        $state.go('studentCourse', {courseid: courseCode});
      }

    };
	});
