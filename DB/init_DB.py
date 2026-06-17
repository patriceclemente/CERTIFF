import users
import depots

def init():
    # users d'abord (table parent),
    # depots et statuts y font référence
    users.create_users_table()
    print("Table users créée.")
    depots.create_history_table()
    print("Table depots créée.")
    depots.create_status_table()
    print("Table statuts créée.")
    
    print("---Base initialisée---")

    users.create_test_user()  # créer un utilisateur de test si la table est vide

if __name__ == "__main__":
    init()