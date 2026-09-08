from django.db import models
from django.db.models import Avg, Sum, Count, Q
from decimal import Decimal
from .models import GradingSystem, GradeRule, PerformanceAnalysis, SubjectPerformance
from marks.models import MarkEntry
from students.models import Student
from datetime import datetime

class GradingEngine:
    """Core grading engine for processing marks"""
    
    def __init__(self, examination, grade_level=None, stream=None):
        self.examination = examination
        self.grade_level = grade_level
        self.stream = stream
        self.grading_system = self._get_grading_system()
        
    def _get_grading_system(self):
        """Get the appropriate grading system"""
        curriculum = self.examination.curriculum
        grade_level = self.examination.grade_level
        
        # Try to find a specific grading system for this grade
        grading_system = GradingSystem.objects.filter(
            curriculum=curriculum,
            grade_level=grade_level,
            is_active=True
        ).first()
        
        if not grading_system:
            # Fall back to curriculum-level grading system
            grading_system = GradingSystem.objects.filter(
                curriculum=curriculum,
                grade_level__isnull=True,
                is_active=True
            ).first()
        
        return grading_system
    
    def _get_grade_rule(self, score, subject=None):
        """Determine grade based on score"""
        if not self.grading_system:
            return None, None, 0
        
        rules = GradeRule.objects.filter(
            grading_system=self.grading_system,
            is_active=True
        )
        
        if subject:
            rules = rules.filter(
                models.Q(subject_type='ALL') | 
                models.Q(subject_type='SPECIFIC', subject=subject)
            )
        else:
            rules = rules.filter(subject_type='ALL')
        
        for rule in rules.order_by('order'):
            if rule.min_score <= score <= rule.max_score:
                return rule.grade, rule.grade_name, rule.points
        
        return None, None, 0
    
    def _get_subject_marks(self, student):
        """Get all marks for a student in this examination"""
        marks = MarkEntry.objects.filter(
            student=student,
            examination=self.examination,
            is_active=True
        ).select_related('subject')
        
        return {mark.subject_id: mark for mark in marks}
    
    def process_student(self, student):
        """Process a single student's marks"""
        marks = self._get_subject_marks(student)
        
        if not marks:
            return None
        
        # Calculate subject performances
        subject_performances = []
        total_score = 0
        total_possible = 0
        max_possible = len(marks) * 100
        
        for subject_id, mark in marks.items():
            score = mark.score or 0
            grade, grade_name, points = self._get_grade_rule(float(score), mark.subject)
            
            subject_performances.append({
                'subject': mark.subject,
                'score': score,
                'grade': grade,
                'grade_name': grade_name,
                'points': points
            })
            
            total_score += float(score)
            total_possible += 100
        
        # Calculate overall performance
        total_possible = total_possible or 1
        average_score = (total_score / total_possible) * 100 if total_possible > 0 else 0
        overall_grade, overall_grade_name, overall_points = self._get_grade_rule(average_score)
        
        return {
            'student': student,
            'marks': marks,
            'subject_performances': subject_performances,
            'total_score': total_score,
            'average_score': average_score,
            'overall_grade': overall_grade,
            'overall_points': overall_points,
            'grade_name': overall_grade_name
        }
    
    def process_examination(self):
        """Process all students for this examination"""
        # Get all students for this class
        if self.grade_level and self.stream:
            students = Student.objects.filter(
                current_grade_level=self.grade_level,
                current_stream=self.stream,
                is_active=True
            )
        else:
            # Get all students in the grade level
            students = Student.objects.filter(
                current_grade_level=self.examination.grade_level,
                is_active=True
            )
        
        results = []
        for student in students:
            result = self.process_student(student)
            if result:
                results.append(result)
        
        # Save results to database
        self._save_results(results)
        
        # Calculate rankings
        self._calculate_rankings(results)
        
        # Identify strengths and weaknesses
        self._analyze_performance(results)
        
        return results
    
    def _save_results(self, results):
        """Save performance analysis to database"""
        for result in results:
            # Create or update PerformanceAnalysis
            analysis, created = PerformanceAnalysis.objects.update_or_create(
                student=result['student'],
                examination=self.examination,
                defaults={
                    'academic_year': self.examination.academic_year,
                    'term': self.examination.term,
                    'total_score': result['total_score'],
                    'average_score': result['average_score'],
                    'overall_grade': result['overall_grade'],
                    'overall_points': result['overall_points'],
                }
            )
            
            # Save subject performances
            SubjectPerformance.objects.filter(analysis=analysis).delete()
            for perf in result['subject_performances']:
                SubjectPerformance.objects.create(
                    analysis=analysis,
                    subject=perf['subject'],
                    score=perf['score'],
                    grade=perf['grade'],
                    points=perf['points']
                )
    
    def _calculate_rankings(self, results):
        """Calculate student rankings"""
        # Sort by average score
        sorted_results = sorted(results, key=lambda x: x['average_score'], reverse=True)
        
        for i, result in enumerate(sorted_results, 1):
            analysis = PerformanceAnalysis.objects.get(
                student=result['student'],
                examination=self.examination
            )
            analysis.position = i
            analysis.class_position = i
            analysis.save()
    
    def _analyze_performance(self, results):
        """Analyze strengths and weaknesses"""
        for result in results:
            analysis = PerformanceAnalysis.objects.get(
                student=result['student'],
                examination=self.examination
            )
            
            # Identify strengths (subjects above average)
            avg_score = result['average_score']
            strengths = []
            weaknesses = []
            
            for perf in result['subject_performances']:
                if perf['score'] >= avg_score + 10:
                    strengths.append({
                        'subject': perf['subject'].name,
                        'score': float(perf['score'])
                    })
                    # Mark as strong
                    subject_perf = SubjectPerformance.objects.get(
                        analysis=analysis,
                        subject=perf['subject']
                    )
                    subject_perf.is_strong = True
                    subject_perf.save()
                    
                elif perf['score'] <= avg_score - 10:
                    weaknesses.append({
                        'subject': perf['subject'].name,
                        'score': float(perf['score'])
                    })
                    # Mark as weak
                    subject_perf = SubjectPerformance.objects.get(
                        analysis=analysis,
                        subject=perf['subject']
                    )
                    subject_perf.is_weak = True
                    subject_perf.save()
            
            analysis.strengths = strengths
            analysis.weaknesses = weaknesses
            
            # Generate improvement suggestions
            improvement_areas = []
            for weak in weaknesses:
                improvement_areas.append(
                    f"Additional attention needed in {weak['subject']} (Score: {weak['score']:.1f}%)"
                )
            analysis.improvement_areas = improvement_areas
            
            analysis.save()
    
    def get_class_report(self):
        """Generate class performance report"""
        analyses = PerformanceAnalysis.objects.filter(
            examination=self.examination
        ).select_related('student')
        
        if not analyses:
            return None
        
        # Calculate class statistics
        total_students = analyses.count()
        avg_score = analyses.aggregate(Avg('average_score'))['average_score__avg'] or 0
        highest_score = analyses.aggregate(Max('average_score'))['average_score__max'] or 0
        lowest_score = analyses.aggregate(Min('average_score'))['average_score__min'] or 0
        
        # Pass rate (assuming 40% is passing)
        pass_count = analyses.filter(average_score__gte=40).count()
        pass_rate = (pass_count / total_students * 100) if total_students > 0 else 0
        
        # Grade distribution
        grade_distribution = {}
        for analysis in analyses:
            grade = analysis.overall_grade or 'N/A'
            grade_distribution[grade] = grade_distribution.get(grade, 0) + 1
        
        # Top students
        top_students = analyses.order_by('-average_score')[:3]
        
        return {
            'total_students': total_students,
            'average_score': avg_score,
            'highest_score': highest_score,
            'lowest_score': lowest_score,
            'pass_rate': pass_rate,
            'pass_count': pass_count,
            'grade_distribution': grade_distribution,
            'top_students': [
                {
                    'name': s.student.full_name,
                    'admission': s.student.admission_number,
                    'score': float(s.average_score),
                    'grade': s.overall_grade
                } for s in top_students
            ]
        }
