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