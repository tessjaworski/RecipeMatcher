import sys

import csv
import sqlite3

from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import *
from PyQt5 import uic
from PyQt5.QtCore import QFile, QTextStream

from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget
from PyQt5.QtGui import QIcon
from PyQt5.uic import loadUi

def create_database():
    conn = sqlite3.connect('recipes.db')
    cur = conn.cursor()

    cur.execute('''
CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY,
    name TEXT,
    ingredients TEXT,
    instructions TEXT
)
''')

    conn.commit()
    conn.close()

def insert_csv_data():
    conn = sqlite3.connect('recipes.db')
    cur = conn.cursor()

    with open('recipes.csv', 'r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            # Split ingredients by comma and add spaces around each
            ingredients_list = [f" {ingredient.strip()} " for ingredient in row['Ingredients'].split(',')]

            # Join ingredients list with commas and insert into database
            ingredients = ', '.join(ingredients_list)
            cur.execute('''
               INSERT INTO recipes (name, ingredients, instructions)
               VALUES (?, ?, ?)
               ''', (row['Title'], ingredients, row['Instructions']))



    conn.commit()
    conn.close()

def fetch_recipes(conn):
    cur = conn.cursor()
    cur.execute("SELECT * FROM recipes")
    rows = cur.fetchall()

    recipes = []
    for row in rows:
        recipe = {
            'id': row[0],
            'name': row[1],
            'ingredients': row[2],
            'instructions': row[3]
        }
        recipes.append(recipe)

    return recipes


class RecipeDetailWindow(QDialog):
    def __init__(self, recipe):
        super().__init__()
        self.setWindowTitle("Recipe Detail")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        layout = QVBoxLayout()

        # Display recipe name
        name_label = QLabel(f"<h2>{recipe['name']}</h2>")
        layout.addWidget(name_label)

        # Display ingredients
        ingredients_html = '<h3>Ingredients:</h3><ul>'
        ingredients_list = self.split_ingredients(recipe['ingredients'].strip("[]"))
        for ingredient in ingredients_list:
            ingredients_html += f'<li>{ingredient.strip()}</li>'
        ingredients_html += '</ul>'

        ingredients_label = QLabel(ingredients_html)
        ingredients_label.setTextFormat(Qt.RichText)
        ingredients_label.setWordWrap(True)
        ingredients_scroll = QScrollArea()
        ingredients_scroll.setWidgetResizable(True)
        ingredients_scroll.setWidget(ingredients_label)
        layout.addWidget(ingredients_scroll)

        # Display instructions
        instructions_label = QLabel(f"<b>Instructions:</b><br/>{recipe['instructions']}")
        instructions_label.setWordWrap(True)
        layout.addWidget(instructions_label)

        self.setLayout(layout)

    def split_ingredients(self, ingredients_str):
            ingredients_list = []
            current_item = ''
            in_quotes = False

            for char in ingredients_str:
                if char == "'":
                    in_quotes = not in_quotes
                elif char == ',' and not in_quotes:
                    ingredients_list.append(current_item.strip())
                    current_item = ''
                else:
                    current_item += char

            # Append the last item
            if current_item:
                ingredients_list.append(current_item.strip())

            return ingredients_list


class RecipeTitlesDialog(QDialog):
    def __init__(self, recipe_titles, parent = None):
        super().__init__(parent = parent)
        self.setWindowTitle('Recipe Titles')
        self.setMinimumWidth(300)

        self.layout = QVBoxLayout()

        self.recipe_titles_set = set()  # To keep track of added recipes
        self.setLayout(self.layout)
        self.add_recipe_titles(recipe_titles)



    def show_recipe_details(self, recipe_id):
        conn = sqlite3.connect('recipes.db')
        cur = conn.cursor()

        # Fetch the recipe details from the database using the recipe ID
        cur.execute("SELECT * FROM recipes WHERE id=?", (recipe_id,))
        row = cur.fetchone()

        conn.close()

        if row:
            recipe = {
                'id': row[0],
                'name': row[1],
                'ingredients': row[2],
                'instructions': row[3]
            }
            recipe_detail_window = RecipeDetailWindow(recipe)
            recipe_detail_window.exec_()

    def add_recipe_titles(self, recipe_titles):
        for recipe in recipe_titles:
            if recipe['id'] not in self.recipe_titles_set:
                self.recipe_titles_set.add(recipe['id'])
                recipe_button = QPushButton(recipe['name'])
                recipe_button.clicked.connect(
                    lambda _, id=recipe['id']: self.show_recipe_details(id))
                self.layout.addWidget(recipe_button)

    def clear_recipe_titles(self):
        # Remove all widgets from the layout and reset the set of recipe titles
        for i in reversed(range(self.layout.count())):
            widget = self.layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()
        self.recipe_titles_set.clear()


class MyGui(QMainWindow):

    def __init__(self):
        super(MyGui,self).__init__()
        loadUi('design1.ui', self)
        self.show()

        style_file = QFile("styleSheet.qss")
        style_file.open(QFile.ReadOnly | QFile.Text)
        stream = QTextStream(style_file)
        style_sheet = stream.readAll()
        self.setStyleSheet(style_sheet)

        #connects to database
        self.conn = sqlite3.connect('recipes.db')
        self.cur = self.conn.cursor()

        self.addButton.clicked.connect(self.add_ingredient)
        self.removeButton.clicked.connect(self.remove_ingredient)
        self.suggestButton.clicked.connect(self.show_suggested_recipes)
        self.loadMoreButton.clicked.connect(self.load_more_recipes)
        self.recipe_offset = 0
        self.recipe_limit = 10
        self.current_recipes = [] #ten current recipes that are being shown to user

        self.suggested_recipes = set()  # empty set to store recipes that have already been suggested

        self.ingredients = []

        self.recipe_titles_dialog = None

        default_font = QFont("Arial", 10)
        self.setFont(default_font)

    def add_ingredient(self):
        ingredient_name = self.ingredientInput.text().strip()
        if ingredient_name:
            self.ingredients.append(ingredient_name)
            self.ingredientList.addItem(ingredient_name)
            self.ingredientInput.clear()

    def remove_ingredient(self):
        selected_items = self.ingredientList.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            ingredient = item.text()
            self.ingredients.remove(ingredient)
            self.ingredientList.takeItem(self.ingredientList.row(item))

    def show_suggested_recipes(self):
            if not self.ingredients:
                QMessageBox.information(self, "Error", "Please add ingredients first!")
                return

            self.recipe_offset = 0
            self.suggested_recipes.clear()
            self.current_recipes.clear()

            self.fetch_initial_recipes()

            if self.current_recipes:
                self.display_recipe_titles()
            else:
                QMessageBox.information(self, "No Recipes Found", "No recipes found with these ingredients.")

    @staticmethod
    def fetch_recipe_titles(ingredients, limit=10):
        conn = sqlite3.connect('recipes.db')  # Connect to your SQLite database
        cur = conn.cursor()

        # Prepare ingredients list for query
        ingredients_str = [ing.lower() for ing in ingredients]

        ingredients_str = [ing.lower() for ing in self.ingredients]
        conditions = [f"LOWER(TRIM(ingredients)) LIKE ?" for _ in ingredients_str]

        # Construct SQL query with parameterized inputs
        query = "SELECT DISTINCT id, name FROM recipes WHERE "
        conditions = []
        for ingredient in ingredients_str:
            conditions.append("LOWER(TRIM(ingredients)) LIKE ?")
        query += " AND ".join(conditions)

        # Limit the number of results
        query += f" LIMIT {limit}"

        # Execute query with parameterized values
        params = ['%' + ing + '%' for ing in ingredients_str]
        cur.execute(query, params)
        rows = cur.fetchall()

        # Convert fetched data into a list of dictionaries
        recipe_titles = [{'id': row[0], 'name': row[1]} for row in rows]

        conn.close()

        return recipe_titles




    def display_recipe_titles(self):


        if not self.current_recipes:
            QMessageBox.information(self, "No Recipes Found", "No recipes found with these ingredients.")

        if self.recipe_titles_dialog is None:
            self.recipe_titles_dialog = RecipeTitlesDialog(self.current_recipes[:10], parent=self)

        else:
            self.update_recipe_display(self.current_recipes[:10])
        self.recipe_titles_dialog.show()

    def fetch_initial_recipes(self):

                self.current_recipes = []
                self.suggested_recipes.clear()
                self.recipe_offset = 0



                ingredients_str = [f" {ing.lower().strip()} " for ing in self.ingredients]
                placeholders = ','.join('?' for _ in self.suggested_recipes)

                conditions_all = [f"LOWER(TRIM(ingredients)) LIKE ?" for _ in ingredients_str]
                query_all = f"""
                       SELECT DISTINCT id, name, ingredients, instructions FROM recipes 
                       WHERE {' AND '.join(conditions_all)}
                       LIMIT {self.recipe_limit} OFFSET {self.recipe_offset}
                   """

                # Execute query to fetch recipes matching all ingredients
                params_all = ['%' + ing + '%' for ing in ingredients_str]
                self.cur.execute(query_all, params_all)
                recipes_all = self.cur.fetchall()



                print(query_all)
                print(params_all)

                print("Fetched recipes:", [recipe[1] for recipe in recipes_all])

                # Add recipes matching all ingredients to current_recipes
                for recipe in recipes_all:
                    recipe_dict = {
                        'id': recipe[0],
                        'name': recipe[1],
                        'ingredients': recipe[2],
                        'instructions': recipe[3]
                    }
                    if recipe_dict['id'] not in self.suggested_recipes:
                        print("Adding recipe:", recipe_dict['name'])
                        self.current_recipes.append(recipe_dict)
                        self.suggested_recipes.add(recipe_dict['id'])

                print("Suggested recipes IDs:", self.suggested_recipes)


                self.recipe_offset += len(recipes_all)



                self.update_recipe_display(self.current_recipes)



    def load_more_recipes(self):

        # Check if there are any suggested recipes to exclude
        if not self.suggested_recipes:
            QMessageBox.information(self, "Error", "No initial recipes found. Click suggest recipes")
            return
        print(self.suggested_recipes)

        # Prepare the query to exclude already suggested recipes
        placeholders = ','.join('?' for _ in self.suggested_recipes)
        ingredients_str = [ing.lower() for ing in self.ingredients]
        conditions = [f"LOWER(TRIM(ingredients)) LIKE ?" for _ in ingredients_str]
        query = f"""
            SELECT * FROM recipes 
            WHERE id NOT IN ({placeholders}) AND {' AND '.join(conditions)}
            LIMIT {self.recipe_limit}
            """

        # Prepare the parameters for the query
        params = list(self.suggested_recipes) + ['%' + ing + '%' for ing in ingredients_str]

        # Execute the query
        self.cur.execute(query, params)
        fetched_recipes = self.cur.fetchall()

        if not fetched_recipes:
            # Handle case when no more recipes are available
            QMessageBox.information(self, "No More Recipes", "No more recipes found.")
            return

        # Process fetched recipes and add to self.current_recipes
        new_recipes = []
        for recipe in fetched_recipes:
            recipe_dict = {
                'id': recipe[0],
                'name': recipe[1],
                'ingredients': recipe[2],
                'instructions': recipe[3]
            }
            if recipe_dict['id'] not in self.suggested_recipes:
                self.suggested_recipes.add(recipe_dict['id'])
                new_recipes.append(recipe_dict)

        # Update self.current_recipes with new_recipes
        self.current_recipes.extend(new_recipes)


        self.recipe_offset += self.recipe_limit

        self.update_recipe_display(new_recipes)

    def update_recipe_display(self, new_recipes):

            if self.recipe_titles_dialog is not None:
                self.recipe_titles_dialog.clear_recipe_titles()  # Clear existing recipes
                self.recipe_titles_dialog.add_recipe_titles(new_recipes)
            else:
                self.recipe_titles_dialog = RecipeTitlesDialog(new_recipes, parent=self)
                self.recipe_titles_dialog.show()

def main():
    create_database()
    insert_csv_data()
    app = QApplication([])
    window = MyGui()
    window.show()
    app.exec()

if __name__ == '__main__':
    main()