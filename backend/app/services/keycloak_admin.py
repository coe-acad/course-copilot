"""
Keycloak Admin API service for managing organizations, groups, and users
Handles organization creation, user management, and role assignments
"""
import logging
from typing import Optional, Dict, List
from keycloak import KeycloakAdmin
from keycloak.exceptions import KeycloakError
from ..config.settings import settings

logger = logging.getLogger(__name__)


class KeycloakAdminService:
    """Service for Keycloak Admin API operations"""
    
    def __init__(self):
        self.server_url = settings.KEYCLOAK_SERVER_URL.rstrip("/")
        self.realm = settings.KEYCLOAK_REALM
        self.client_id = settings.KEYCLOAK_ADMIN_CLIENT_ID
        self.username = settings.KEYCLOAK_ADMIN_USERNAME
        self.password = settings.KEYCLOAK_ADMIN_PASSWORD
        
        # Initialize Keycloak Admin client
        # Note: Admin user authenticates in "master" realm, but we operate on CourseCopilot realm
        try:
            # Create admin client - authenticate in master, but set target realm
            self.admin = KeycloakAdmin(
                server_url=self.server_url,
                username=self.username,
                password=self.password,
                realm_name="master",  # Admin user authenticates in master realm
                client_id=self.client_id,
                verify=True
            )
            
            # CRITICAL: Switch to our target realm for all operations
            # This must be done before any operations
            self.admin.realm_name = self.realm
            
            # Verify we're in the correct realm by getting realm info
            try:
                realm_info = self.admin.get_realm(self.realm)
                logger.info(f"Keycloak Admin client initialized successfully for realm: {self.realm} (ID: {realm_info.get('id')})")
            except Exception as verify_error:
                logger.warning(f"Could not verify realm switch: {str(verify_error)}")
                logger.info(f"Keycloak Admin client initialized (realm verification skipped)")
        except Exception as e:
            logger.error(f"Failed to initialize Keycloak Admin client: {str(e)}")
            raise
    
    def _ensure_realm(self):
        """Ensure admin client is using the correct realm"""
        if self.admin.realm_name != self.realm:
            logger.warning(f"Realm mismatch detected. Switching from {self.admin.realm_name} to {self.realm}")
            self.admin.realm_name = self.realm
    
    # ========== Organization (Group) Management ==========
    
    def create_organization(self, org_name: str) -> Optional[Dict]:
        """
        Create a new organization (top-level group)
        Returns group info if successful, None otherwise
        """
        try:
            # Ensure we're in the correct realm
            self._ensure_realm()
            logger.info(f"Creating organization '{org_name}' in realm: {self.admin.realm_name}")
            
            # create_group returns the group ID (string), not the full group object
            group_id = self.admin.create_group({
                "name": org_name
            })
            logger.info(f"Created organization group: {org_name} with ID: {group_id}")
            
            # Fetch the full group details
            group = self.admin.get_group(group_id)
            logger.info(f"Organization created in realm: {self.admin.realm_name}, path: {group.get('path')}")
            return group
        except KeycloakError as e:
            logger.error(f"Failed to create organization {org_name}: {str(e)}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating organization {org_name}: {str(e)}", exc_info=True)
            return None
    
    def _get_admin_token(self) -> str:
        """Get admin access token via REST API"""
        import requests
        token_url = f"{self.server_url}/realms/master/protocol/openid-connect/token"
        token_data = {
            "client_id": self.client_id,
            "username": self.username,
            "password": self.password,
            "grant_type": "password"
        }
        token_response = requests.post(token_url, data=token_data, timeout=10)
        token_response.raise_for_status()
        return token_response.json()["access_token"]
    
    def _get_all_groups_via_rest(self) -> List[Dict]:
        """Get all groups using REST API directly (more reliable than python-keycloak get_groups)"""
        try:
            import requests
            admin_token = self._get_admin_token()
            
            # Get groups via REST API
            groups_url = f"{self.server_url}/admin/realms/{self.realm}/groups"
            headers = {"Authorization": f"Bearer {admin_token}"}
            groups_response = requests.get(groups_url, headers=headers, timeout=10)
            groups_response.raise_for_status()
            return groups_response.json()
        except Exception as e:
            logger.error(f"Failed to get groups via REST API: {str(e)}")
            # Fallback to python-keycloak method
            try:
                return self.admin.get_groups()
            except:
                return []
    
    def _get_group_children_via_rest(self, group_id: str) -> List[Dict]:
        """Get group children using REST API directly"""
        try:
            import requests
            admin_token = self._get_admin_token()
            
            # Get group children via REST API
            children_url = f"{self.server_url}/admin/realms/{self.realm}/groups/{group_id}/children"
            headers = {"Authorization": f"Bearer {admin_token}"}
            children_response = requests.get(children_url, headers=headers, timeout=10)
            children_response.raise_for_status()
            return children_response.json()
        except Exception as e:
            logger.error(f"Failed to get group children via REST API: {str(e)}")
            # Fallback to python-keycloak method
            try:
                return self.admin.get_group_children(group_id)
            except:
                return []
    
    def get_organization(self, org_name: str) -> Optional[Dict]:
        """Get organization group by name"""
        try:
            groups = self._get_all_groups_via_rest()
            for group in groups:
                if group.get("name") == org_name:
                    return group
            return None
        except KeycloakError as e:
            logger.error(f"Failed to get organization {org_name}: {str(e)}")
            return None
    
    def create_org_subgroups(self, org_id: str, org_name: str) -> Dict[str, Optional[Dict]]:
        """
        Create Admins and Instructors subgroups for an organization
        Returns dict with 'admins' and 'instructors' group info
        """
        result = {"admins": None, "instructors": None}
        
        try:
            # Create Admins subgroup - create_group returns group ID
            admins_group_id = self.admin.create_group({
                "name": "Admins"
            }, parent=org_id)
            # Fetch full group details
            result["admins"] = self.admin.get_group(admins_group_id)
            logger.info(f"Created Admins subgroup for {org_name} with ID: {admins_group_id}")
            
            # Create Instructors subgroup
            instructors_group_id = self.admin.create_group({
                "name": "Instructors"
            }, parent=org_id)
            # Fetch full group details
            result["instructors"] = self.admin.get_group(instructors_group_id)
            logger.info(f"Created Instructors subgroup for {org_name} with ID: {instructors_group_id}")
            
            return result
        except KeycloakError as e:
            logger.error(f"Failed to create subgroups for {org_name}: {str(e)}", exc_info=True)
            return result
        except Exception as e:
            logger.error(f"Unexpected error creating subgroups for {org_name}: {str(e)}", exc_info=True)
            return result
    
    def create_realm_role_if_not_exists(self, role_name: str) -> bool:
        """
        Create a realm role if it doesn't exist
        Returns True if role exists or was created, False otherwise
        """
        try:
            # Check if role exists
            try:
                role = self.admin.get_realm_role(role_name)
                if role:
                    logger.info(f"Role {role_name} already exists")
                    return True
            except KeycloakError:
                # Role doesn't exist, create it
                pass
            
            # Create the role
            self.admin.create_realm_role({
                "name": role_name,
                "description": f"Realm role: {role_name}"
            })
            logger.info(f"Created realm role: {role_name}")
            return True
        except KeycloakError as e:
            logger.error(f"Failed to create role {role_name}: {str(e)}")
            return False
    
    def assign_role_to_group(self, group_id: str, role_name: str) -> bool:
        """
        Assign a realm role to a group
        This makes all users in that group automatically get the role
        """
        try:
            # First ensure the role exists
            if not self.create_realm_role_if_not_exists(role_name):
                logger.error(f"Could not create or find role {role_name}")
                return False
            
            # Get the role
            role = self.admin.get_realm_role(role_name)
            if not role:
                logger.error(f"Role {role_name} not found after creation attempt")
                return False
            
            # Assign role to group
            self.admin.assign_group_realm_roles(group_id, [role])
            logger.info(f"Assigned role {role_name} to group {group_id}")
            return True
        except KeycloakError as e:
            logger.error(f"Failed to assign role {role_name} to group: {str(e)}")
            return False
    
    def setup_organization_with_roles(self, org_name: str) -> Optional[Dict]:
        """
        Complete setup: Create org, create subgroups, assign roles
        Returns organization info with subgroup IDs
        """
        try:
            # Step 1: Create organization
            logger.info(f"Step 1: Creating organization {org_name}")
            org = self.create_organization(org_name)
            if not org:
                logger.error(f"Step 1 failed: Could not create organization {org_name}")
                return None
            
            org_id = org.get("id")
            logger.info(f"Step 1 success: Organization created with ID {org_id}")
            
            # Step 2: Create subgroups
            logger.info(f"Step 2: Creating subgroups for {org_name}")
            subgroups = self.create_org_subgroups(org_id, org_name)
            if not subgroups["admins"] or not subgroups["instructors"]:
                logger.error(f"Step 2 failed: Could not create subgroups. Admins: {subgroups['admins']}, Instructors: {subgroups['instructors']}")
                return None
            
            logger.info(f"Step 2 success: Subgroups created")
            
            # Step 3: Assign roles to subgroups
            logger.info(f"Step 3: Assigning roles to subgroups")
            admins_group_id = subgroups["admins"].get("id")
            instructors_group_id = subgroups["instructors"].get("id")
            
            admins_role_success = self.assign_role_to_group(admins_group_id, "org-admin")
            instructors_role_success = self.assign_role_to_group(instructors_group_id, "instructor")
            
            if not admins_role_success:
                logger.warning(f"Step 3 warning: Failed to assign org-admin role to Admins group")
            if not instructors_role_success:
                logger.warning(f"Step 3 warning: Failed to assign instructor role to Instructors group")
            
            # Continue even if role assignment fails (roles might not exist yet)
            logger.info(f"Successfully set up organization {org_name}")
            
            return {
                "organization": org,
                "admins_group": subgroups["admins"],
                "instructors_group": subgroups["instructors"]
            }
        except Exception as e:
            logger.error(f"Failed to setup organization {org_name}: {str(e)}", exc_info=True)
            return None
    
    # ========== User Management ==========
    
    def create_user(self, email: str, password: str, first_name: str = "", last_name: str = "") -> Optional[str]:
        """
        Create a new user in Keycloak
        Returns user ID if successful, None otherwise
        """
        try:
            # Ensure we're in the correct realm
            self._ensure_realm()
            logger.info(f"Creating user '{email}' in realm: {self.admin.realm_name}")
            
            # Use REST API to ensure user is created in correct realm
            import requests
            admin_token = self._get_admin_token()
            
            user_data = {
                "email": email,
                "username": email,
                "firstName": first_name,
                "lastName": last_name,
                "enabled": True,
                "emailVerified": True,
                "credentials": [{
                    "type": "password",
                    "value": password,
                    "temporary": False
                }]
            }
            
            # Create user via REST API
            users_url = f"{self.server_url}/admin/realms/{self.realm}/users"
            headers = {
                "Authorization": f"Bearer {admin_token}",
                "Content-Type": "application/json"
            }
            
            create_response = requests.post(users_url, json=user_data, headers=headers, timeout=10)
            create_response.raise_for_status()
            
            # Get the user ID from the Location header
            location = create_response.headers.get("Location", "")
            if location:
                user_id = location.split("/")[-1]
                logger.info(f"Created user: {email} with ID: {user_id}")
                
                # Set password separately to ensure it's set correctly
                password_url = f"{self.server_url}/admin/realms/{self.realm}/users/{user_id}/reset-password"
                password_payload = {
                    "type": "password",
                    "value": password,
                    "temporary": False
                }
                password_response = requests.put(password_url, json=password_payload, headers=headers, timeout=10)
                if password_response.status_code == 204:
                    logger.info(f"Password set for user: {email}")
                else:
                    logger.warning(f"Password set returned status {password_response.status_code}")
                
                return user_id
            else:
                # Fallback: find user by email
                users = self.admin.get_users({"email": email})
                if users:
                    return users[0].get("id")
                return None
        except Exception as e:
            logger.error(f"Failed to create user {email}: {str(e)}", exc_info=True)
            return None
    
    def add_user_to_group(self, user_id: str, group_id: str) -> bool:
        """Add a user to a group using REST API"""
        try:
            # Ensure we're in the correct realm
            self._ensure_realm()
            
            # Use REST API to ensure correct realm
            import requests
            admin_token = self._get_admin_token()
            
            add_group_url = f"{self.server_url}/admin/realms/{self.realm}/users/{user_id}/groups/{group_id}"
            headers = {"Authorization": f"Bearer {admin_token}"}
            
            response = requests.put(add_group_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            logger.info(f"Added user {user_id} to group {group_id} in realm {self.realm}")
            return True
        except Exception as e:
            logger.error(f"Failed to add user to group: {str(e)}", exc_info=True)
            return False
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email using REST API"""
        try:
            # Ensure we're in the correct realm
            self._ensure_realm()
            
            # Use REST API to ensure correct realm
            import requests
            admin_token = self._get_admin_token()
            
            users_url = f"{self.server_url}/admin/realms/{self.realm}/users"
            headers = {"Authorization": f"Bearer {admin_token}"}
            
            response = requests.get(users_url, headers=headers, params={"email": email}, timeout=10)
            response.raise_for_status()
            
            users = response.json()
            if users and len(users) > 0:
                return users[0]
            return None
        except Exception as e:
            logger.error(f"Failed to get user by email {email}: {str(e)}")
            return None
    
    def update_user_email_verified(self, user_id: str, email_verified: bool = True) -> bool:
        """Update user's email verified status"""
        try:
            self.admin.update_user(user_id, {"emailVerified": email_verified})
            logger.info(f"Updated emailVerified status for user {user_id} to {email_verified}")
            return True
        except KeycloakError as e:
            logger.error(f"Failed to update user email verified status: {str(e)}")
            return False
    
    def create_org_admin(self, org_name: str, email: str, password: str, first_name: str = "", last_name: str = "") -> Optional[Dict]:
        """
        Create an organization admin user and add them to the org's Admins group
        Returns user info if successful
        """
        try:
            # Step 1: Get organization
            org = self.get_organization(org_name)
            if not org:
                logger.error(f"Organization {org_name} not found")
                return None
            
            # Step 2: Get Admins subgroup using REST API
            org_id = org.get("id")
            org_groups = self._get_group_children_via_rest(org_id)
            admins_group = None
            for group in org_groups:
                if group.get("name") == "Admins":
                    admins_group = group
                    break
            
            if not admins_group:
                logger.error(f"Admins subgroup not found for {org_name}")
                return None
            
            # Step 3: Create user
            user_id = self.create_user(email, password, first_name, last_name)
            if not user_id:
                return None
            
            # Step 4: Add user to Admins group (automatically gets org-admin role)
            self.add_user_to_group(user_id, admins_group.get("id"))
            
            logger.info(f"Created org admin {email} for {org_name}")
            return {"user_id": user_id, "email": email, "org_name": org_name}
        except Exception as e:
            logger.error(f"Failed to create org admin: {str(e)}")
            return None
    
    def create_instructor(self, org_name: str, email: str, password: str, first_name: str = "", last_name: str = "") -> Optional[Dict]:
        """
        Create an instructor user and add them to the org's Instructors group
        Returns user info if successful
        """
        try:
            # Step 1: Get organization
            org = self.get_organization(org_name)
            if not org:
                logger.error(f"Organization {org_name} not found")
                return None
            
            # Step 2: Get Instructors subgroup using REST API
            org_id = org.get("id")
            org_groups = self._get_group_children_via_rest(org_id)
            instructors_group = None
            for group in org_groups:
                if group.get("name") == "Instructors":
                    instructors_group = group
                    break
            
            if not instructors_group:
                logger.error(f"Instructors subgroup not found for {org_name}")
                return None
            
            # Step 3: Create user
            user_id = self.create_user(email, password, first_name, last_name)
            if not user_id:
                return None
            
            # Step 4: Add user to Instructors group (automatically gets instructor role)
            self.add_user_to_group(user_id, instructors_group.get("id"))
            
            logger.info(f"Created instructor {email} for {org_name}")
            return {"user_id": user_id, "email": email, "org_name": org_name}
        except Exception as e:
            logger.error(f"Failed to create instructor: {str(e)}")
            return None


# Create global instance
try:
    keycloak_admin = KeycloakAdminService()
except Exception as e:
    logger.error(f"Failed to initialize Keycloak Admin service: {str(e)}")
    keycloak_admin = None

 