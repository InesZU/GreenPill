from abc import ABC, abstractmethod


class DataManagerInterface(ABC):
    @abstractmethod
    def add_user(self, user):
        pass

    @abstractmethod
    def get_user(self, user_id):
        pass

    @abstractmethod
    def get_all_users(self):
        pass

    @abstractmethod
    def delete_user(self, user_id):
        pass

    # Remedies management
    @abstractmethod
    def get_remedies(self, limit=10, offset=0):
        pass

    @abstractmethod
    def get_remedy_by_name(self, name):
        pass

    @abstractmethod
    def get_remedies_by_complaint(self, complaint_id):
        pass

    # Complaints management
    @abstractmethod
    def get_complaints(self, limit=10):
        pass
