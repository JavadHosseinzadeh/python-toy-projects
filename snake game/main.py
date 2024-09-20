import sys
import random
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel
from PyQt5.QtCore import Qt, QTimer, QRect
from PyQt5.QtGui import QPainter, QColor, QFont

class SnakeGame(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Snake Game")
        self.setGeometry(100, 100, 600, 600)
        self.grid_size = 20

        # Initialize game variables first
        self.init_game_variables()

        # Initialize UI
        self.init_ui()

        # Initialize timers
        self.init_timers()

    def init_ui(self):
        # Set up UI elements
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.score_label = QLabel(f"Score: {self.score}", self)  # Use the initialized score
        self.score_label.setAlignment(Qt.AlignCenter)
        self.score_label.setFont(QFont("Arial", 16))
        self.layout.addWidget(self.score_label)

        self.start_button = QPushButton("Start Game", self)
        self.start_button.clicked.connect(self.start_game)
        self.layout.addWidget(self.start_button)

        self.restart_button = QPushButton("Restart Game", self)
        self.restart_button.clicked.connect(self.restart_game)
        self.layout.addWidget(self.restart_button)
        self.restart_button.setVisible(False)

        self.exit_button = QPushButton("Exit", self)
        self.exit_button.clicked.connect(self.close)
        self.layout.addWidget(self.exit_button)
        self.exit_button.setVisible(False)

    def init_game_variables(self):
        self.snake = [(100, 100), (80, 100), (60, 100)]
        self.direction = 'RIGHT'
        self.next_direction = 'RIGHT'
        self.food = None
        self.obstacles = []
        self.score = 0
        self.game_over_flag = False
        self.paused = False
        self.game_started = False

    def init_timers(self):
        # Timer for game loop
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.game_loop)

    def resizeEvent(self, event):
        self.rows = self.height() // self.grid_size
        self.cols = self.width() // self.grid_size

    def start_game(self):
        self.start_button.setVisible(False)
        self.restart_button.setVisible(False)
        self.exit_button.setVisible(False)
        self.init_game_variables()  # Reinitialize variables when starting the game
        self.food = self.place_food()
        self.obstacles = self.place_obstacles()
        self.score = 0
        self.game_over_flag = False
        self.game_started = True
        self.paused = False
        self.timer.start(100)
        self.repaint()

    def restart_game(self):
        self.start_game()

    def place_food(self):
        while True:
            x = random.randint(0, self.cols - 1) * self.grid_size
            y = random.randint(0, self.rows - 1) * self.grid_size
            if (x, y) not in self.snake and (x, y) not in self.obstacles:
                return (x, y)

    def place_obstacles(self):
        obstacle_count = int(0.03 * self.rows * self.cols)  # 3% of the grid
        obstacles = []
        for _ in range(obstacle_count):
            while True:
                x = random.randint(0, self.cols - 1) * self.grid_size
                y = random.randint(0, self.rows - 1) * self.grid_size
                if (x, y) not in self.snake and (x, y) != self.food and (x, y) not in obstacles:
                    obstacles.append((x, y))
                    break
        return obstacles

    def paintEvent(self, event):
        if not self.game_started:
            return

        painter = QPainter(self)
        self.draw_snake(painter)
        self.draw_food(painter)
        self.draw_obstacles(painter)

        if self.game_over_flag:
            self.draw_game_over_screen(painter)
        elif self.paused:
            self.draw_pause_screen(painter)

    def draw_snake(self, painter):
        painter.setBrush(QColor(0, 255, 0))
        for segment in self.snake:
            painter.drawRect(segment[0], segment[1], self.grid_size, self.grid_size)

    def draw_food(self, painter):
        painter.setBrush(QColor(255, 0, 0))
        if self.food:
            painter.drawRect(self.food[0], self.food[1], self.grid_size, self.grid_size)

    def draw_obstacles(self, painter):
        painter.setBrush(QColor(0, 0, 255))
        for obs in self.obstacles:
            painter.drawRect(obs[0], obs[1], self.grid_size, self.grid_size)

    def draw_game_over_screen(self, painter):
        painter.setBrush(QColor(255, 0, 0, 128))
        painter.drawRect(0, 0, self.width(), self.height())
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Arial", 24))
        painter.drawText(self.rect(), Qt.AlignCenter, f"Game Over!\nScore: {self.score}")

    def draw_pause_screen(self, painter):
        painter.setBrush(QColor(0, 0, 0, 128))
        painter.drawRect(0, 0, self.width(), self.height())
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Arial", 24))
        painter.drawText(self.rect(), Qt.AlignCenter, "Game Paused\nPress P to Resume")

    def keyPressEvent(self, event):
        if not self.game_started or self.game_over_flag:
            return

        key = event.key()

        if key == Qt.Key_A and self.direction != 'RIGHT':  # Left
            self.next_direction = 'LEFT'
        elif key == Qt.Key_D and self.direction != 'LEFT':  # Right
            self.next_direction = 'RIGHT'
        elif key == Qt.Key_W and self.direction != 'DOWN':  # Up
            self.next_direction = 'UP'
        elif key == Qt.Key_S and self.direction != 'UP':  # Down
            self.next_direction = 'DOWN'
        elif key == Qt.Key_P:
            self.toggle_pause()

    def game_loop(self):
        if not self.game_over_flag and self.game_started and not self.paused:
            if (self.next_direction == 'LEFT' and self.direction != 'RIGHT') or \
               (self.next_direction == 'RIGHT' and self.direction != 'LEFT') or \
               (self.next_direction == 'UP' and self.direction != 'DOWN') or \
               (self.next_direction == 'DOWN' and self.direction != 'UP'):
                self.direction = self.next_direction

            self.move_snake()
            self.check_collisions()
            self.repaint()
            self.score_label.setText(f"Score: {self.score}")

    def move_snake(self):
        head_x, head_y = self.snake[0]
        if self.direction == 'LEFT':
            head_x -= self.grid_size
        elif self.direction == 'RIGHT':
            head_x += self.grid_size
        elif self.direction == 'UP':
            head_y -= self.grid_size
        elif self.direction == 'DOWN':
            head_y += self.grid_size

        self.snake = [(head_x, head_y)] + self.snake[:-1]

        if self.snake[0] == self.food:
            self.snake.append(self.snake[-1])  # Grow the snake
            self.food = self.place_food()
            self.score += 1

    def check_collisions(self):
        head_x, head_y = self.snake[0]

        if head_x < 0 or head_x >= self.width() or head_y < 0 or head_y >= self.height():
            self.game_over()

        if len(self.snake) > 3 and self.snake[0] in self.snake[1:]:
            self.game_over()

        if (head_x, head_y) in self.obstacles:
            self.game_over()

    def game_over(self):
        self.timer.stop()
        self.game_over_flag = True
        self.restart_button.setVisible(True)
        self.exit_button.setVisible(True)

    def toggle_pause(self):
        if self.paused:
            self.timer.start(100)
            self.paused = False
        else:
            self.timer.stop()
            self.paused = True
        self.repaint()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    game = SnakeGame()
    game.showFullScreen()  # Launch the game in fullscreen mode
    sys.exit(app.exec_())
