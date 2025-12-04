"""
Seeding script to populate system_configurations collection with initial data.
Run this script once to populate curriculum, assessment, and settings data.

Usage:
    python seed_configurations.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.mongo import create_configuration, get_one_from_collection

# Curriculum configurations
curriculum_configs = [
    {
        "_id": "curr-brainstorm",
        "type": "curriculum",
        "key": "brainstorm",
        "label": "Brainstorm",
        "desc": "Generate and organize initial ideas for your course curriculum.",
        "url": "brainstorm",
        "order": 1
    },
    {
        "_id": "curr-course-outcomes",
        "type": "curriculum",
        "key": "course-outcomes",
        "label": "Course Outcomes",
        "desc": "Set clear learning goals students are expected to achieve by the end of the course.",
        "url": "course-outcomes",
        "order": 2
    },
    {
        "_id": "curr-modules",
        "type": "curriculum",
        "key": "modules",
        "label": "Modules",
        "desc": "Organize content into structured modules and focused topics for easy navigation.",
        "url": "modules",
        "order": 3
    },
    {
        "_id": "curr-lecture",
        "type": "curriculum",
        "key": "lecture",
        "label": "Lecture",
        "desc": "Plan each session with defined objectives, activities, and resources.",
        "url": "lecture",
        "order": 4
    },
    {
        "_id": "curr-course-notes",
        "type": "curriculum",
        "key": "course-notes",
        "label": "Course Notes",
        "desc": "Add notes to support student understanding and revision.",
        "url": "course-notes",
        "order": 5
    },
    {
        "_id": "curr-concept-plan",
        "type": "curriculum",
        "key": "concept-plan",
        "label": "Concept Plan",
        "desc": "Generate a session-by-session concept plan aligned with best-practice learning design.",
        "url": "concept-plan",
        "order": 6
    }
]

# Assessment configurations
assessment_configs = [
    {
        "_id": "assess-project",
        "type": "assessment",
        "key": "project",
        "label": "Project",
        "desc": "Encourage deep learning through hands-on, outcome-driven assignments.",
        "url": "project",
        "order": 1
    },
    {
        "_id": "assess-activity",
        "type": "assessment",
        "key": "activity",
        "label": "Activity",
        "desc": "Engage students with interactive tasks that reinforce learning through application.",
        "url": "activity",
        "order": 2
    },
    {
        "_id": "assess-quiz",
        "type": "assessment",
        "key": "quiz",
        "label": "Quiz",
        "desc": "Assess student understanding with short, focused questions on key concepts.",
        "url": "quiz",
        "order": 3
    },
    {
        "_id": "assess-question-paper",
        "type": "assessment",
        "key": "question-paper",
        "label": "Question Paper",
        "desc": "Create formal assessments to evaluate overall learning and subject mastery.",
        "url": "question-paper",
        "order": 4
    },
    {
        "_id": "assess-mark-scheme",
        "type": "assessment",
        "key": "mark-scheme",
        "label": "Mark Scheme",
        "desc": "Create detailed marking criteria and rubrics for fair and consistent assessment.(Select the Question Paper to generate the Mark Scheme)",
        "url": "mark-scheme",
        "order": 5
    },
    {
        "_id": "assess-mock-interview",
        "type": "assessment",
        "key": "mock-interview",
        "label": "Mock Interview",
        "desc": "Simulate real-world interviews to prepare students for job readiness.",
        "url": "mock-interview",
        "order": 6
    }
]

# Settings configurations
settings_configs = [
    {
        "_id": "setting-course-level",
        "type": "setting",
        "category": "course_level",
        "label": "Course level",
        "options": ["Year 1", "Year 2", "Year 3", "Year 4"]
    },
    {
        "_id": "setting-study-area",
        "type": "setting",
        "category": "study_area",
        "label": "Study area",
        "options": [
            "AI & Decentralised Technologies",
            "Life Sciences",
            "Energy Sciences",
            "eMobility",
            "Climate Change",
            "Connected Intelligence"
        ]
    },
    {
        "_id": "setting-pedagogical",
        "type": "setting",
        "category": "pedagogical_components",
        "label": "Pedagogical Components",
        "options": [
            "Theory",
            "Project",
            "Research",
            "Laboratory Experiments",
            "Unplugged Activities",
            "Programming Activities"
        ]
    }
]

def seed_configurations():
    """Seed all configurations into the database"""
    print("Starting database seeding...")
    
    all_configs = curriculum_configs + assessment_configs + settings_configs
    
    created_count = 0
    skipped_count = 0
    
    for config in all_configs:
        # Check if configuration already exists
        existing = get_one_from_collection("system_configurations", {"_id": config["_id"]})
        
        if existing:
            print(f"⏭️  Skipped: {config['_id']} (already exists)")
            skipped_count += 1
        else:
            create_configuration(config)
            print(f"✅ Created: {config['_id']}")
            created_count += 1
    
    print("\n" + "="*50)
    print("Seeding completed!")
    print(f"✅ Created: {created_count} configurations")
    print(f"⏭️  Skipped: {skipped_count} configurations (already existed)")
    print(f"📊 Total: {len(all_configs)} configurations")
    print("="*50)

if __name__ == "__main__":
    try:
        seed_configurations()
    except Exception as e:
        print(f"\n❌ Error during seeding: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

