from ..services.firebase import db
import logging
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

class StorageService:
    def create_course(self, course_id: str, course_data: Dict):
        try:
            db.collection("courses").document(course_id).set(course_data)
            logger.info(f"Created course: {course_id}")
        except Exception as e:
            logger.error(f"Error creating course {course_id}: {str(e)}")
            raise

    def get_course(self, course_id: str, user_id: Optional[str] = None) -> Optional[Dict]:
        try:
            doc = db.collection("courses").document(course_id).get()
            if doc.exists:
                course_data = doc.to_dict()
                if user_id is not None and course_data.get("user_id") != user_id:
                    logger.error(f"User {user_id} not authorized for course {course_id}")
                    return None
                return course_data
            logger.error(f"Course not found: {course_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting course {course_id}: {str(e)}")
            raise

    def get_user_courses(self, user_id: str) -> List[Dict]:
        try:
            docs = db.collection("courses").where("user_id", "==", user_id).stream()
            courses = []
            for doc in docs:
                course_data = doc.to_dict()
                course_data["courseId"] = doc.id
                courses.append(course_data)
            logger.info(f"Fetched {len(courses)} courses for user {user_id}")
            return courses
        except Exception as e:
            logger.error(f"Error fetching courses for user {user_id}: {str(e)}")
            raise

    def update_course(self, course_id: str, course_data: Dict):
        try:
            db.collection("courses").document(course_id).set(course_data, merge=True)
            logger.info(f"Updated course: {course_id}")
        except Exception as e:
            logger.error(f"Error updating course {course_id}: {str(e)}")
            raise

    def delete_course(self, course_id: str):
        try:
            db.collection("courses").document(course_id).delete()
            logger.info(f"Deleted course: {course_id}")
        except Exception as e:
            logger.error(f"Error deleting course {course_id}: {str(e)}")
            raise

    def get_resources(self, course_id: str, thread_id: Optional[str] = None, user_id: Optional[str] = None) -> list:
        try:
            course = self.get_course(course_id, user_id)
            if not course:
                logger.error(f"Course not found or unauthorized: {course_id}")
                return []
            resources = []
            if thread_id:
                docs = db.collection("courses").document(course_id).collection("brainstorm").document(thread_id).collection("resources").stream()
            else:
                docs = db.collection("courses").document(course_id).collection("resources").stream()
            for doc in docs:
                data = doc.to_dict()
                data["fileId"] = doc.id
                resources.append(data)
            return resources
        except Exception as e:
            logger.error(f"Error getting resources for course {course_id}: {str(e)}")
            raise

    def create_resource(self, course_id: str, file_id: str, resource_data: Dict, thread_id: Optional[str] = None):
        try:
            if thread_id:
                db.collection("courses").document(course_id).collection("brainstorm").document(thread_id).collection("resources").document(file_id).set(resource_data)
                logger.info(f"Created resource {file_id} for course {course_id} under thread {thread_id} in Firebase")
            else:
                db.collection("courses").document(course_id).collection("resources").document(file_id).set(resource_data)
                logger.info(f"Created resource {file_id} for course {course_id} in global resources")
            logger.info(f"Created resource {file_id} for course {course_id}")
        except Exception as e:
            logger.error(f"Error creating resource {file_id} for course {course_id}: {str(e)}")
            raise

    def get_resource(self, course_id: str, file_id: str) -> Optional[Dict]:
        try:
            # First try course-level resources
            doc = db.collection("courses").document(course_id).collection("resources").document(file_id).get()
            if doc.exists:
                data = doc.to_dict()
                data["fileId"] = doc.id
                return data
            
            # If not found, search in asset-level resources (brainstorm threads)
            try:
                brainstorm_docs = db.collection("courses").document(course_id).collection("brainstorm").stream()
                for thread_doc in brainstorm_docs:
                    thread_id = thread_doc.id
                    doc = db.collection("courses").document(course_id).collection("brainstorm").document(thread_id).collection("resources").document(file_id).get()
                    if doc.exists:
                        data = doc.to_dict()
                        data["fileId"] = doc.id
                        data["thread_id"] = thread_id
                        return data
            except Exception as e:
                logger.warning(f"Could not search asset-level resources: {e}")
            
            logger.error(f"Resource not found: {file_id} in course {course_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting resource {file_id} for course {course_id}: {str(e)}")
            raise

    def update_resource(self, course_id: str, file_id: str, resource_data: Dict, thread_id: Optional[str] = None):
        try:
            if thread_id:
                db.collection("courses").document(course_id).collection("brainstorm").document(thread_id).collection("resources").document(file_id).set(resource_data, merge=True)
            else:
                db.collection("courses").document(course_id).collection("resources").document(file_id).set(resource_data, merge=True)
            logger.info(f"Updated resource {file_id} for course {course_id}")
        except Exception as e:
            logger.error(f"Error updating resource {file_id} for course {course_id}: {str(e)}")
            raise

    def delete_all_resources(self, course_id: str, thread_id: Optional[str] = None):
        try:
            if thread_id:
                docs = db.collection("courses").document(course_id).collection("brainstorm").document(thread_id).collection("resources").stream()
            else:
                docs = db.collection("courses").document(course_id).collection("resources").stream()
            for doc in docs:
                doc.reference.delete()
                logger.info(f"Deleted resource {doc.id} for course {course_id}")
        except Exception as e:
            logger.error(f"Error deleting resources for course {course_id}: {str(e)}")
            raise

    def delete_resource(self, course_id: str, file_id: str, thread_id: Optional[str] = None):
        try:
            if thread_id:
                db.collection("courses").document(course_id).collection("brainstorm").document(thread_id).collection("resources").document(file_id).delete()
            else:
                db.collection("courses").document(course_id).collection("resources").document(file_id).delete()
            logger.info(f"Deleted resource {file_id} for course {course_id}")
        except Exception as e:
            logger.error(f"Error deleting resource {file_id} for course {course_id}: {str(e)}")
            raise

    def save_chat_message(self, course_id: str, thread_id: str, message_data: dict):
        db.collection("courses").document(course_id).collection("brainstorm").document(thread_id).collection("messages").add(message_data)

    def save_brainstorm_message(self, course_id: str, thread_id: str, message_data: dict):
        """Save a message specifically for brainstorm threads"""
        try:
            db.collection("courses").document(course_id).collection("brainstorm").document(thread_id).collection("messages").add(message_data)
            logger.info(f"Saved brainstorm message for course {course_id}, thread {thread_id}")
        except Exception as e:
            logger.error(f"Error saving brainstorm message: {str(e)}")
            raise

    def get_chat_history(self, course_id: str, thread_id: str) -> list:
        messages_ref = db.collection("courses").document(course_id).collection("brainstorm").document(thread_id).collection("messages")
        messages = messages_ref.order_by("timestamp").stream()
        return [msg.to_dict() for msg in messages]

    def create_asset_thread(self, course_id: str, asset_name: str, thread_id: str):
        # Create a new asset-named collection (e.g., 'brainstorm') and document for the thread
        db.collection("courses").document(course_id).collection(asset_name).document(thread_id).set({"created_at": datetime.utcnow().isoformat()})
        logger.info(f"Created asset thread {thread_id} under {asset_name} for course {course_id} in Firebase")

    def get_brainstorm_messages(self, course_id: str, thread_id: str, user_id: str) -> list:
        try:
            messages_ref = db.collection("courses").document(course_id).collection("brainstorm").document(thread_id).collection("messages")
            messages = messages_ref.order_by("timestamp").stream()
            return [msg.to_dict() for msg in messages]
        except Exception as e:
            logger.error(f"Error getting brainstorm messages for course {course_id}, thread {thread_id}: {str(e)}")
            raise

    def get_brainstorm_resources(self, course_id: str, thread_id: str, user_id: str) -> Dict:
        try:
            resources = {}
            docs = db.collection("courses").document(course_id).collection("brainstorm").document(thread_id).collection("resources").stream()
            for doc in docs:
                resources[doc.id] = doc.to_dict()
            return resources
        except Exception as e:
            logger.error(f"Error getting brainstorm resources for course {course_id}, thread {thread_id}: {str(e)}")
            raise

    def save_course_outcomes_message(self, course_id: str, thread_id: str, message_data: dict):
        """Save a message specifically for course outcomes threads"""
        try:
            db.collection("courses").document(course_id).collection("course_outcomes").document(thread_id).collection("messages").add(message_data)
            logger.info(f"Saved course outcomes message for course {course_id}, thread {thread_id}")
        except Exception as e:
            logger.error(f"Error saving course outcomes message: {str(e)}")
            raise

    def get_course_outcomes_history(self, course_id: str, thread_id: str) -> list:
        """Get chat history for course outcomes threads"""
        try:
            messages_ref = db.collection("courses").document(course_id).collection("course_outcomes").document(thread_id).collection("messages")
            messages = messages_ref.order_by("timestamp").stream()
            return [msg.to_dict() for msg in messages]
        except Exception as e:
            logger.error(f"Error getting course outcomes history for course {course_id}, thread {thread_id}: {str(e)}")
            raise

    def get_course_outcomes_threads(self, course_id: str, user_id: str) -> list:
        """Get all course outcomes threads for a course"""
        try:
            threads = []
            docs = db.collection("courses").document(course_id).collection("course_outcomes").stream()
            for doc in docs:
                thread_data = doc.to_dict()
                thread_data["thread_id"] = doc.id
                threads.append(thread_data)
            logger.info(f"Found {len(threads)} course outcomes threads for course {course_id}")
            return threads
        except Exception as e:
            logger.error(f"Error getting course outcomes threads for course {course_id}: {str(e)}")
            raise

storage_service = StorageService()