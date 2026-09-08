from django.test import SimpleTestCase

from .services import (
    get_performance_level,
    assessment_completion,
    performance_distribution,
    top_learners,
    best_gender,
    calculate_improvement,
    most_improved,
    learners_requiring_support,
    learning_area_average,
    best_learning_areas,
    weakest_learning_areas,
    generate_general_insight,
)


class CBCFunctionsTest(SimpleTestCase):

    # ========================================================
    # PERFORMANCE LEVEL TESTS
    # ========================================================

    def test_pl4(self):
        self.assertEqual(
            get_performance_level(80),
            "PL4"
        )

    def test_pl3(self):
        self.assertEqual(
            get_performance_level(60),
            "PL3"
        )

    def test_pl2(self):
        self.assertEqual(
            get_performance_level(30),
            "PL2"
        )

    def test_pl1(self):
        self.assertEqual(
            get_performance_level(10),
            "PL1"
        )

    def test_empty_score(self):
        self.assertIsNone(
            get_performance_level(None)
        )

    # ========================================================
    # COMPLETION TESTS
    # ========================================================

    def test_assessment_completion(self):

        result = assessment_completion(
            total_learners=40,
            assessed_learners=35
        )

        self.assertEqual(
            result["expected"],
            40
        )

        self.assertEqual(
            result["assessed"],
            35
        )

        self.assertEqual(
            result["not_assessed"],
            5
        )

        self.assertEqual(
            result["completion_rate"],
            87.5
        )

    def test_zero_learners(self):

        result = assessment_completion(
            total_learners=0,
            assessed_learners=0
        )

        self.assertEqual(
            result["completion_rate"],
            0
        )

    # ========================================================
    # PERFORMANCE DISTRIBUTION
    # ========================================================

    def test_performance_distribution(self):

        results = [
            {"level": "PL4"},
            {"level": "PL4"},
            {"level": "PL3"},
            {"level": "PL2"},
            {"level": "PL1"},
            {"level": "PL1"},
        ]

        result = performance_distribution(results)

        self.assertEqual(result["PL4"], 2)
        self.assertEqual(result["PL3"], 1)
        self.assertEqual(result["PL2"], 1)
        self.assertEqual(result["PL1"], 2)

    # ========================================================
    # TOP LEARNERS
    # ========================================================

    def test_top_three_learners(self):

        results = [
            {"student": "A", "score": 65},
            {"student": "B", "score": 90},
            {"student": "C", "score": 75},
            {"student": "D", "score": 95},
            {"student": "E", "score": 85},
        ]

        result = top_learners(
            results,
            limit=3
        )

        self.assertEqual(
            result[0]["student"],
            "D"
        )

        self.assertEqual(
            result[1]["student"],
            "B"
        )

        self.assertEqual(
            result[2]["student"],
            "E"
        )

    # ========================================================
    # BEST BOY / GIRL
    # ========================================================

    def test_best_boy(self):

        results = [
            {
                "student": "John",
                "gender": "M",
                "score": 80
            },
            {
                "student": "Peter",
                "gender": "M",
                "score": 95
            },
            {
                "student": "Mary",
                "gender": "F",
                "score": 98
            },
        ]

        result = best_gender(
            results,
            gender="M"
        )

        self.assertEqual(
            result[0]["student"],
            "Peter"
        )

    def test_best_girl(self):

        results = [
            {
                "student": "John",
                "gender": "M",
                "score": 80
            },
            {
                "student": "Mary",
                "gender": "F",
                "score": 98
            },
            {
                "student": "Jane",
                "gender": "F",
                "score": 90
            },
        ]

        result = best_gender(
            results,
            gender="F"
        )

        self.assertEqual(
            result[0]["student"],
            "Mary"
        )

    # ========================================================
    # IMPROVEMENT
    # ========================================================

    def test_calculate_improvement(self):

        result = calculate_improvement(
            current_score=80,
            previous_score=65
        )

        self.assertEqual(
            result,
            15
        )

    def test_negative_improvement(self):

        result = calculate_improvement(
            current_score=60,
            previous_score=75
        )

        self.assertEqual(
            result,
            -15
        )

    def test_most_improved(self):

        results = [
            {
                "student": "A",
                "current_score": 80,
                "previous_score": 70
            },
            {
                "student": "B",
                "current_score": 90,
                "previous_score": 60
            },
            {
                "student": "C",
                "current_score": 70,
                "previous_score": 65
            },
        ]

        result = most_improved(
            results,
            limit=3
        )

        self.assertEqual(
            result[0]["student"],
            "B"
        )

        self.assertEqual(
            result[0]["improvement"],
            30
        )

    # ========================================================
    # SUPPORT LEARNERS
    # ========================================================

    def test_learners_requiring_support(self):

        results = [
            {"student": "A", "level": "PL4"},
            {"student": "B", "level": "PL3"},
            {"student": "C", "level": "PL2"},
            {"student": "D", "level": "PL1"},
        ]

        result = learners_requiring_support(results)

        self.assertEqual(
            len(result),
            2
        )

        self.assertEqual(
            result[0]["student"],
            "C"
        )

        self.assertEqual(
            result[1]["student"],
            "D"
        )

    # ========================================================
    # LEARNING AREA ANALYSIS
    # ========================================================

    def test_learning_area_average(self):

        results = [
            {
                "learning_area": "Mathematics",
                "score": 80
            },
            {
                "learning_area": "Mathematics",
                "score": 60
            },
            {
                "learning_area": "English",
                "score": 70
            },
            {
                "learning_area": "English",
                "score": 90
            },
        ]

        result = learning_area_average(results)

        self.assertEqual(
            result["Mathematics"],
            70
        )

        self.assertEqual(
            result["English"],
            80
        )

    def test_best_learning_area(self):

        results = [
            {
                "learning_area": "Mathematics",
                "score": 60
            },
            {
                "learning_area": "English",
                "score": 85
            },
            {
                "learning_area": "Science",
                "score": 75
            },
        ]

        result = best_learning_areas(
            results,
            limit=1
        )

        self.assertEqual(
            result[0][0],
            "English"
        )

    def test_weakest_learning_area(self):

        results = [
            {
                "learning_area": "Mathematics",
                "score": 60
            },
            {
                "learning_area": "English",
                "score": 85
            },
            {
                "learning_area": "Science",
                "score": 75
            },
        ]

        result = weakest_learning_areas(
            results,
            limit=1
        )

        self.assertEqual(
            result[0][0],
            "Mathematics"
        )

    # ========================================================
    # GENERAL INSIGHT
    # ========================================================

    def test_general_insight(self):

        results = [
            {"level": "PL4"},
            {"level": "PL4"},
            {"level": "PL3"},
            {"level": "PL3"},
            {"level": "PL4"},
        ]

        result = generate_general_insight(results)

        self.assertIn(
            "meeting or exceeding",
            result
        )

    def test_empty_assessment_insight(self):

        result = generate_general_insight([])

        self.assertEqual(
            result,
            "No assessment data is available."
        )
