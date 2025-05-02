from spyne import Application, rpc, ServiceBase, Unicode, Integer, Float, Array, Boolean
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from wsgiref.simple_server import make_server
import oracledb
from datetime import datetime
import upstash_redis as redis
import os

# Upstash Redis configuration
redis_client = redis.Redis(url="https://fine-hamster-32812.upstash.io", token="your-key")

# Oracle DB configuration(EDIT THIS AREA!!!)
oracle_user = os.getenv("ORACLE_USER", "YourUsername")
oracle_password = os.getenv("ORACLE_PASSWORD", "YourPassword")
oracle_dsn = os.getenv("ORACLE_DSN", "oracle-xe/XE")

dsn = oracledb.makedsn("oracle-xe", 1521, sid="XE")
connection = oracledb.connect(user=oracle_user, password=oracle_password, dsn=dsn)

# Rate Limiting Middleware
def rate_limit_middleware(ctx):
    try:
        # Get user ID or IP address
        user_id = ctx.in_header.user_id if hasattr(ctx.in_header, "user_id") else ctx.transport.req_env.get("REMOTE_ADDR")
        
        # Create rate limit key (user-based)
        key = f"rate_limit:{user_id}"
        print(f"Rate limit key: {key}")
        
        # Get current request count
        current_count = redis_client.get(key)
        print(f"Current count: {current_count}")
        
        # If request count exceeds 5, return an error
        if current_count and int(current_count) >= 5:
            raise Exception("Too many requests")
        
        # Increment request count or create a new key
        if not current_count:
            redis_client.set(key, 1, ex=30)  # Limit for 30 seconds
            print("New key created.")
        else:
            redis_client.incr(key)
            print("Key incremented.")
        
        # Continue with the request
        return True
    except Exception as e:
        print(f"Rate limiting middleware error: {e}")
        raise Exception("Rate limit exceeded")

# User Service
class UserService(ServiceBase):
    @rpc(Unicode, Unicode, Unicode, _returns=Unicode)
    def register(ctx, username, password, role):
        try:
            cursor = connection.cursor()
            cursor.execute("INSERT INTO USERACCOUNTS (USERNAME, PASSWORD, ROLE) VALUES (:1, :2, :3)", 
                           (username, password, role))
            connection.commit()
            return "User registered successfully"
        except Exception as e:
            return f"Error: {str(e)}"

    @rpc(Unicode, Unicode, _returns=Unicode)
    def login(ctx, username, password):
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT USER_ID FROM USERACCOUNTS WHERE USERNAME = :1 AND PASSWORD = :2", (username, password))
            user = cursor.fetchone()
            if not user:
                return "Invalid credentials"
            token = str(hash(f"{username}{password}"))
            redis_client.set(token, user[0])
            return f"Logged in with token: {token}"
        except Exception as e:
            return f"Error: {str(e)}"

    @rpc(Integer, Unicode, Unicode, Unicode, _returns=Unicode)
    def update_user(ctx, user_id, username, password, role):
        try:
            if not rate_limit_middleware(ctx):
                return "Rate limit exceeded"
            cursor = connection.cursor()
            cursor.execute("UPDATE USERACCOUNTS SET USERNAME = :1, PASSWORD = :2, ROLE = :3 WHERE USER_ID = :4", 
                           (username, password, role, user_id))
            connection.commit()
            return "User updated successfully"
        except Exception as e:
            return f"Error: {str(e)}"

    @rpc(Integer, _returns=Unicode)
    def delete_user(ctx, user_id):
        try:
            if not rate_limit_middleware(ctx):
                return "Rate limit exceeded"
            cursor = connection.cursor()
            cursor.execute("DELETE FROM USERACCOUNTS WHERE USER_ID = :1", (user_id,))
            connection.commit()
            return "User deleted successfully"
        except Exception as e:
            return f"Error: {str(e)}"

# Job Service
class JobService(ServiceBase):
    @rpc(Unicode, Unicode, Unicode, _returns=Unicode)
    def create_job(ctx, title, description, department):
        try:
            if not rate_limit_middleware(ctx):
                return "Rate limit exceeded"
            cursor = connection.cursor()
            cursor.execute("INSERT INTO JOBS (TITLE, DESCRIPTION, DEPARTMENT) VALUES (:1, :2, :3)", 
                           (title, description, department))
            connection.commit()
            return "Job created successfully"
        except Exception as e:
            return f"Error: {str(e)}"

    @rpc(Integer, Unicode, Unicode, Unicode, _returns=Unicode)
    def update_job(ctx, job_id, title, description, department):
        try:
            if not rate_limit_middleware(ctx):
                return "Rate limit exceeded"
            cursor = connection.cursor()
            cursor.execute("UPDATE JOBS SET TITLE = :1, DESCRIPTION = :2, DEPARTMENT = :3 WHERE JOB_ID = :4", 
                           (title, description, department, job_id))
            connection.commit()
            return "Job updated successfully"
        except Exception as e:
            return f"Error: {str(e)}"

    @rpc(Integer, _returns=Unicode)
    def delete_job(ctx, job_id):
        try:
            if not rate_limit_middleware(ctx):
                return "Rate limit exceeded"
            cursor = connection.cursor()
            cursor.execute("DELETE FROM JOBS WHERE JOB_ID = :1", (job_id,))
            connection.commit()
            return "Job deleted successfully"
        except Exception as e:
            return f"Error: {str(e)}"

    @rpc(_returns=Array(Unicode))
    def get_jobs(ctx):
        try:
            if not rate_limit_middleware(ctx):
                return "Rate limit exceeded"
            cursor = connection.cursor()
            cursor.execute("SELECT JOB_ID, TITLE, DESCRIPTION, DEPARTMENT FROM JOBS")
            jobs = cursor.fetchall()
            return [f"Job ID: {job[0]}, Title: {job[1]}, Description: {job[2]}, Department: {job[3]}" for job in jobs]
        except Exception as e:
            return [f"Error: {str(e)}"]

# Application Service
class ApplicationService(ServiceBase):
    @rpc(Integer, Integer, Unicode, _returns=Unicode)
    def apply_for_job(ctx, user_id, job_id, status):
        try:
            if not rate_limit_middleware(ctx):
                return "Rate limit exceeded"
            cursor = connection.cursor()
            cursor.execute("INSERT INTO APPLICATIONS (USER_ID, JOB_ID, STATUS) VALUES (:1, :2, :3)", 
                           (user_id, job_id, status))
            connection.commit()
            return "Application submitted successfully"
        except Exception as e:
            return f"Error: {str(e)}"

    @rpc(Integer, Integer, Integer, Unicode, _returns=Unicode)
    def update_application(ctx, application_id, user_id, job_id, status):
        try:
            if not rate_limit_middleware(ctx):
                return "Rate limit exceeded"
            cursor = connection.cursor()
            cursor.execute("UPDATE APPLICATIONS SET USER_ID = :1, JOB_ID = :2, STATUS = :3 WHERE APPLICATION_ID = :4", 
                           (user_id, job_id, status, application_id))
            connection.commit()
            return "Application updated successfully"
        except Exception as e:
            return f"Error: {str(e)}"

    @rpc(Integer, _returns=Unicode)
    def delete_application(ctx, application_id):
        try:
            if not rate_limit_middleware(ctx):
                return "Rate limit exceeded"
            cursor = connection.cursor()
            cursor.execute("DELETE FROM APPLICATIONS WHERE APPLICATION_ID = :1", (application_id,))
            connection.commit()
            return "Application deleted successfully"
        except Exception as e:
            return f"Error: {str(e)}"

    @rpc(_returns=Array(Unicode))
    def get_applications(ctx):
        try:
            if not rate_limit_middleware(ctx):
                return "Rate limit exceeded"
            cursor = connection.cursor()
            cursor.execute("SELECT APPLICATION_ID, USER_ID, JOB_ID, STATUS FROM APPLICATIONS")
            applications = cursor.fetchall()
            return [f"Application ID: {app[0]}, User ID: {app[1]}, Job ID: {app[2]}, Status: {app[3]}" for app in applications]
        except Exception as e:
            return [f"Error: {str(e)}"]

# Interview Service
class InterviewService(ServiceBase):
    @rpc(Integer, Integer, Unicode, Unicode, _returns=Unicode)
    def schedule_interview(ctx, user_id, job_id, interview_date, interview_result):
        try:
            if not rate_limit_middleware(ctx):
                return "Rate limit exceeded"
            interview_date = datetime.fromisoformat(interview_date)
            cursor = connection.cursor()
            cursor.execute("INSERT INTO INTERVIEWS (USER_ID, JOB_ID, INTERVIEW_DATE, INTERVIEW_RESULT) VALUES (:1, :2, :3, :4)", 
                           (user_id, job_id, interview_date, interview_result))
            connection.commit()
            return "Interview scheduled successfully"
        except Exception as e:
            return f"Error: {str(e)}"

    @rpc(Integer, Integer, Integer, Unicode, Unicode, _returns=Unicode)
    def update_interview(ctx, interview_id, user_id, job_id, interview_date, interview_result):
        try:
            if not rate_limit_middleware(ctx):
                return "Rate limit exceeded"
            interview_date = datetime.fromisoformat(interview_date)
            cursor = connection.cursor()
            cursor.execute("UPDATE INTERVIEWS SET USER_ID = :1, JOB_ID = :2, INTERVIEW_DATE = :3, INTERVIEW_RESULT = :4 WHERE INTERVIEW_ID = :5", 
                           (user_id, job_id, interview_date, interview_result, interview_id))
            connection.commit()
            return "Interview updated successfully"
        except Exception as e:
            return f"Error: {str(e)}"

    @rpc(Integer, _returns=Unicode)
    def delete_interview(ctx, interview_id):
        try:
            if not rate_limit_middleware(ctx):
                return "Rate limit exceeded"
            cursor = connection.cursor()
            cursor.execute("DELETE FROM INTERVIEWS WHERE INTERVIEW_ID = :1", (interview_id,))
            connection.commit()
            return "Interview deleted successfully"
        except Exception as e:
            return f"Error: {str(e)}"

    @rpc(_returns=Array(Unicode))
    def get_interviews(ctx):
        try:
            if not rate_limit_middleware(ctx):
                return "Rate limit exceeded"
            cursor = connection.cursor()
            cursor.execute("SELECT INTERVIEW_ID, USER_ID, JOB_ID, INTERVIEW_DATE, INTERVIEW_RESULT FROM INTERVIEWS")
            interviews = cursor.fetchall()
            return [f"Interview ID: {intv[0]}, User ID: {intv[1]}, Job ID: {intv[2]}, Date: {intv[3]}, Result: {intv[4]}" for intv in interviews]
        except Exception as e:
            return [f"Error: {str(e)}"]

# Create the SOAP application
application = Application([UserService, JobService, ApplicationService, InterviewService],
                          tns='soap_api',
                          in_protocol=Soap11(validator='lxml'),
                          out_protocol=Soap11())

# Wrap the Spyne application with a WsgiApplication
wsgi_application = WsgiApplication(application)

if __name__ == '__main__':
    server = make_server('0.0.0.0', 8000, wsgi_application)
    print("SOAP service running on http://0.0.0.0:8000")
    server.serve_forever()