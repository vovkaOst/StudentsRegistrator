/**
 * Created by marzuz on 24.12.16.
 */

'use strict';

angular.module('apsiFrontendApp')
	.controller('RegisterToCourseCtrl', function($http, $scope, $state, $stateParams, Restangular) {

    Restangular.oneUrl('courses', 'http://localhost:8000/courses/?registered=false').get()
      .then(function(toRegister) {
        console.log(toRegister);
        $scope.records = toRegister;
        for (var i = 0; i < $scope.records.length; i++) {
           if ($scope.records[i].state === 0){
             $scope.records[i].state = "Otwarta";
           } else {
             $scope.records[i].state = "Zamknieta";
           }
        }
    });


    $scope.backClick = function () {
      console.log('back to registered');
      $state.go('studentCourses');
    };

    $scope.registerClick = function (id) {
        Restangular.oneUrl('courses', 'http://localhost:8000/courses/'+id+'/registration/').put()
        .then(function() {
          console.log(id+' register');
          $state.reload();
      });
    };

	});
