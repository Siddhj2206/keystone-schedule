"""
Comprehensive semester test for the NumPy scheduler.

Scenario:
- 5 month semester (Dec 1 - Apr 30)
- 7 subjects, each with ~15 topics
- Each subject has:
  - 1 Final exam (40%)
  - 2 Midterm exams (15% each)
  - 3 Quizzes (10% each)
- Total: 7 subjects × 6 assessments = 42 assessments
"""

import time
from datetime import datetime, timedelta
from src.scheduler import (
    generate_schedule,
    ScheduleRequest,
    Topic,
    Assessment,
    TopicStatus,
)


def create_semester_data():
    """Create realistic semester test data."""

    subjects = [
        ("math", "Mathematics"),
        ("physics", "Physics"),
        ("chemistry", "Chemistry"),
        ("biology", "Biology"),
        ("english", "English"),
        ("history", "History"),
        ("computer", "Computer Science"),
    ]

    # Semester dates
    semester_start = datetime(2024, 12, 1)
    semester_end = datetime(2025, 4, 30)

    # Create topics: ~15 per subject = 105 total
    topics = []
    for subj_id, subj_name in subjects:
        n_topics = 15
        for i in range(n_topics):
            topics.append(
                Topic(
                    id=f"{subj_id}-{i}",
                    subject_id=subj_id,
                    title=f"{subj_name} Chapter {i + 1}",
                    est_minutes=60,  # 1 hour per topic
                    current_mastery=0.0,
                    status=TopicStatus.pending,
                    sort_order=i,
                )
            )

    # Create assessments for each subject
    assessments = []

    for subj_id, subj_name in subjects:
        topic_ids = [f"{subj_id}-{i}" for i in range(15)]

        # Quiz 1 - Week 3 (covers topics 1-3)
        assessments.append(
            Assessment(
                id=f"{subj_id}-quiz1",
                subject_id=subj_id,
                title=f"{subj_name} Quiz 1",
                date=int((semester_start + timedelta(days=21)).timestamp() * 1000),
                weightage=10,
                topic_ids=topic_ids[:3],
            )
        )

        # Quiz 2 - Week 6 (covers topics 4-6)
        assessments.append(
            Assessment(
                id=f"{subj_id}-quiz2",
                subject_id=subj_id,
                title=f"{subj_name} Quiz 2",
                date=int((semester_start + timedelta(days=42)).timestamp() * 1000),
                weightage=10,
                topic_ids=topic_ids[3:6],
            )
        )

        # Midterm 1 - Week 7 (covers topics 1-7)
        assessments.append(
            Assessment(
                id=f"{subj_id}-midterm1",
                subject_id=subj_id,
                title=f"{subj_name} Midterm 1",
                date=int((semester_start + timedelta(days=49)).timestamp() * 1000),
                weightage=15,
                topic_ids=topic_ids[:7],
            )
        )

        # Quiz 3 - Week 10 (covers topics 8-10)
        assessments.append(
            Assessment(
                id=f"{subj_id}-quiz3",
                subject_id=subj_id,
                title=f"{subj_name} Quiz 3",
                date=int((semester_start + timedelta(days=70)).timestamp() * 1000),
                weightage=10,
                topic_ids=topic_ids[7:10],
            )
        )

        # Midterm 2 - Week 12 (covers topics 1-12)
        assessments.append(
            Assessment(
                id=f"{subj_id}-midterm2",
                subject_id=subj_id,
                title=f"{subj_name} Midterm 2",
                date=int((semester_start + timedelta(days=84)).timestamp() * 1000),
                weightage=15,
                topic_ids=topic_ids[:12],
            )
        )

        # Final - Week 20 (covers all topics)
        assessments.append(
            Assessment(
                id=f"{subj_id}-final",
                subject_id=subj_id,
                title=f"{subj_name} Final Exam",
                date=int((semester_start + timedelta(days=140)).timestamp() * 1000),
                weightage=40,
                topic_ids=topic_ids,
            )
        )

    return topics, assessments, semester_start, semester_end


def run_semester_test():
    """Run the full semester test."""

    print("=" * 70)
    print("SEMESTER SCHEDULER TEST")
    print("=" * 70)
    print()

    # Create test data
    topics, assessments, start_date, end_date = create_semester_data()

    print("TEST CONFIGURATION")
    print("-" * 40)
    print(
        f"Semester: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
    )
    print(f"Duration: {(end_date - start_date).days + 1} days")
    print(f"Subjects: 7")
    print(f"Topics: {len(topics)} ({len(topics) // 7} per subject)")
    print(f"Assessments: {len(assessments)} ({len(assessments) // 7} per subject)")
    print()

    # Assessment breakdown
    print("ASSESSMENTS PER SUBJECT:")
    print("-" * 40)
    print("  - 3 Quizzes (10% each) = 30%")
    print("  - 2 Midterms (15% each) = 30%")
    print("  - 1 Final (40%) = 40%")
    print("  - Total: 100%")
    print()

    # Study hours: 3 hours weekdays, 2 hours weekends
    study_hours = {
        0: 120,  # Sunday - 2 hrs
        1: 180,  # Monday - 3 hrs
        2: 180,  # Tuesday - 3 hrs
        3: 180,  # Wednesday - 3 hrs
        4: 180,  # Thursday - 3 hrs
        5: 180,  # Friday - 3 hrs
        6: 120,  # Saturday - 2 hrs
    }

    weekly_hours = sum(study_hours.values())
    print(f"STUDY SCHEDULE:")
    print("-" * 40)
    print(f"  Weekdays: 3 hours/day")
    print(f"  Weekends: 2 hours/day")
    print(f"  Weekly total: {weekly_hours // 60} hours")
    print()

    # Create request
    request = ScheduleRequest(
        topics=topics,
        assessments=assessments,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        study_hours=study_hours,
    )

    # Generate schedule
    print("GENERATING SCHEDULE...")
    print("-" * 40)

    start_time = time.perf_counter()
    result = generate_schedule(request)
    elapsed = time.perf_counter() - start_time

    print(f"  Time: {elapsed * 1000:.1f}ms")
    print(f"  Days scheduled: {result.total_days}")
    print(
        f"  Total study time: {result.total_study_minutes} min ({result.total_study_minutes // 60} hours)"
    )
    print(f"  Topics covered: {result.topics_covered}/{len(topics)}")
    print()

    # Analyze results
    print("SCHEDULE ANALYSIS")
    print("=" * 70)

    # Time per subject
    subject_time = {}
    subject_topics_covered = {}
    for plan in result.daily_plans:
        for task in plan.tasks:
            subj = task.subject_id
            subject_time[subj] = subject_time.get(subj, 0) + task.duration_minutes
            if subj not in subject_topics_covered:
                subject_topics_covered[subj] = set()
            subject_topics_covered[subj].add(task.topic_id)

    print("\nTIME PER SUBJECT:")
    print("-" * 40)
    for subj in sorted(subject_time.keys()):
        time_min = subject_time[subj]
        topics_done = len(subject_topics_covered.get(subj, set()))
        print(
            f"  {subj:12s}: {time_min:4d} min ({time_min // 60:2d}h) - {topics_done}/15 topics"
        )

    total_subject_time = sum(subject_time.values())
    print(
        f"  {'TOTAL':12s}: {total_subject_time:4d} min ({total_subject_time // 60:2d}h)"
    )

    # Check topic completion
    print("\nTOPIC COMPLETION:")
    print("-" * 40)

    topic_time = {}
    for plan in result.daily_plans:
        for task in plan.tasks:
            tid = task.topic_id
            topic_time[tid] = topic_time.get(tid, 0) + task.duration_minutes

    incomplete = []
    for topic in topics:
        expected = int(topic.est_minutes * 1.5)  # mastery multiplier
        actual = topic_time.get(topic.id, 0)
        if actual < expected:
            incomplete.append((topic.id, actual, expected))

    if incomplete:
        print(f"  Incomplete topics: {len(incomplete)}")
        for tid, actual, expected in incomplete[:5]:
            print(f"    {tid}: {actual}/{expected} min")
        if len(incomplete) > 5:
            print(f"    ... and {len(incomplete) - 5} more")
    else:
        print("  All topics completed!")

    # Sample schedule output
    print("\n" + "=" * 70)
    print("SAMPLE SCHEDULE (First 2 weeks)")
    print("=" * 70)

    for day_idx, plan in enumerate(result.daily_plans[:14]):
        if plan.tasks:
            date_str = plan.date
            print(f"\n{date_str} ({plan.total_minutes}/{plan.available_minutes} min):")

            # Group by subject
            by_subject = {}
            for task in plan.tasks:
                subj = task.subject_id
                if subj not in by_subject:
                    by_subject[subj] = []
                by_subject[subj].append(task)

            for subj in sorted(by_subject.keys()):
                tasks = by_subject[subj]
                total_dur = sum(t.duration_minutes for t in tasks)
                topics_list = list(set(t.topic_title for t in tasks))
                is_exam = any(t.priority_score > 0.5 for t in tasks)
                exam_marker = " [EXAM PREP]" if is_exam else ""
                print(
                    f"  {subj:12s}: {total_dur:3d}min - {', '.join(topics_list[:2])}{exam_marker}"
                )

    # Exam week analysis
    print("\n" + "=" * 70)
    print("EXAM WEEK ANALYSIS")
    print("=" * 70)

    # Find days around first quiz (week 3, day 21)
    quiz1_day = 21
    print(f"\nWeek of Quiz 1 (Day {quiz1_day}):")
    for day_idx in range(
        max(0, quiz1_day - 3), min(len(result.daily_plans), quiz1_day + 2)
    ):
        plan = result.daily_plans[day_idx]
        if plan.tasks:
            exam_tasks = [t for t in plan.tasks if t.priority_score > 0.5]
            if exam_tasks:
                subjects = set(t.subject_id for t in exam_tasks)
                print(
                    f"  Day {day_idx}: {len(exam_tasks)} exam prep tasks for {', '.join(subjects)}"
                )

    # Find days around midterm 1 (week 7, day 49)
    midterm1_day = 49
    print(f"\nWeek of Midterm 1 (Day {midterm1_day}):")
    for day_idx in range(
        max(0, midterm1_day - 5), min(len(result.daily_plans), midterm1_day + 2)
    ):
        plan = result.daily_plans[day_idx]
        if plan.tasks:
            exam_tasks = [t for t in plan.tasks if t.priority_score > 0.5]
            if exam_tasks:
                subjects = set(t.subject_id for t in exam_tasks)
                print(
                    f"  Day {day_idx}: {len(exam_tasks)} exam prep tasks for {', '.join(subjects)}"
                )

    # Find days around final (week 20, day 140)
    final_day = 140
    print(f"\nWeek of Finals (Day {final_day}):")
    for day_idx in range(
        max(0, final_day - 7), min(len(result.daily_plans), final_day + 2)
    ):
        plan = result.daily_plans[day_idx]
        if plan.tasks:
            exam_tasks = [t for t in plan.tasks if t.priority_score > 0.5]
            if exam_tasks:
                subjects = set(t.subject_id for t in exam_tasks)
                print(
                    f"  Day {day_idx}: {len(exam_tasks)} exam prep tasks for {', '.join(subjects)}"
                )

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)

    return result


if __name__ == "__main__":
    run_semester_test()
