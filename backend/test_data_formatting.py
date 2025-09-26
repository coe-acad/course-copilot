#!/usr/bin/env python3
"""
Test script for the data formatting functionality
Usage: python test_data_formatting.py <course_id> <user_id>
"""

import sys
import os
import json
from datetime import datetime

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

try:
    from app.utils.data_formating import (
        get_formatted_course_data, 
        get_formatted_course_data_dict,
        fetch_course_data
    )
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running this from the backend directory")
    sys.exit(1)

def test_data_formatting(course_id: str, user_id: str):
    """
    Test the data formatting functions with the provided course ID and user ID
    """
    print("=" * 60)
    print("COURSE DATA FORMATTING TEST")
    print("=" * 60)
    print(f"Course ID: {course_id}")
    print(f"User ID: {user_id}")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    try:
        # Test 1: Get formatted data as dictionary (for analysis)
        print("\n1. FETCHING COURSE DATA...")
        print("-" * 40)
        
        dict_data = get_formatted_course_data_dict(course_id, user_id)
        
        if "error" in dict_data:
            print(f"❌ Error: {dict_data['error']}")
            return
        
        print("✅ Successfully fetched course data!")
        
        # Display summary information
        course_info = dict_data.get('course_info', {})
        assets = dict_data.get('assets', [])
        
        print(f"\n📊 DATA SUMMARY:")
        print(f"   Course Name: {course_info.get('course_name', 'N/A')}")
        print(f"   Course ID: {course_info.get('course_id', 'N/A')}")
        print(f"   User ID: {course_info.get('user_id', 'N/A')}")
        print(f"   Number of Assets: {len(assets)}")
        
        # Display course information
        print(f"\n📋 COURSE INFORMATION:")
        for key, value in course_info.items():
            if key == 'settings' and isinstance(value, dict):
                print(f"   {key}:")
                for setting_key, setting_value in value.items():
                    print(f"      {setting_key}: {setting_value}")
            else:
                print(f"   {key}: {value}")
        
        # Display assets
        print(f"\n📁 ASSETS:")
        if assets:
            for i, asset in enumerate(assets, 1):
                print(f"   Asset {i}: {asset.get('asset_name', 'N/A')}")
                print(f"      Type: {asset.get('asset_type', 'N/A')}")
                print(f"      Category: {asset.get('asset_category', 'N/A')}")
                print(f"      Last Updated: {asset.get('last_updated_at', 'N/A')}")
                print(f"      Content Preview: {asset.get('asset_content', '')[:100]}...")
                print()
        else:
            print("   No assets found")
        
        # Test 2: Get JSON output
        print(f"\n2. JSON OUTPUT TEST:")
        print("-" * 40)
        
        json_data = get_formatted_course_data(course_id, user_id)
        
        if json_data.startswith('{"error"'):
            print(f"❌ JSON Error: {json_data}")
        else:
            print("✅ Successfully generated JSON output!")
            print(f"   JSON length: {len(json_data)} characters")
            
            # Option to save JSON to file
            save_json = input("\n💾 Save JSON to file? (y/n): ").lower().strip()
            if save_json == 'y':
                filename = f"course_data_{course_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(json_data)
                print(f"✅ JSON saved to: {filename}")
        
        print(f"\n🎉 Test completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

def show_usage():
    """Show usage instructions"""
    print("USAGE:")
    print("  python test_data_formatting.py <course_id> <user_id>")
    print()
    print("EXAMPLE:")
    print("  python test_data_formatting.py 0bdc4cda-4adb-4286-9b29-ab6e6560d23d user123")
    print()
    print("ARGUMENTS:")
    print("  course_id  - The UUID of the course to test")
    print("  user_id    - The user ID who owns the course")
    print()
    print("OUTPUT FORMAT:")
    print("  The function now returns a simple JSON structure with:")
    print("  - course_info: Basic course information (name, description, settings, etc.)")
    print("  - assets: Array of all assets with their content and metadata")
    print()
    print("NOTE:")
    print("  Make sure you're running this from the backend directory")
    print("  and that the course exists and the user has access to it")

def main():
    """Main function"""
    if len(sys.argv) != 3:
        print("❌ Error: Missing required arguments")
        print()
        show_usage()
        sys.exit(1)
    
    course_id = sys.argv[1]
    user_id = sys.argv[2]
    
    # Validate course_id format (basic UUID check)
    if len(course_id) != 36 or course_id.count('-') != 4:
        print(f"⚠️  Warning: Course ID '{course_id}' doesn't look like a standard UUID")
        proceed = input("Continue anyway? (y/n): ").lower().strip()
        if proceed != 'y':
            print("Test cancelled")
            sys.exit(1)
    
    test_data_formatting(course_id, user_id)

if __name__ == "__main__":
    main()
