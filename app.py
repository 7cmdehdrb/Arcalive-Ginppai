import sys
import os
import requests
import urllib.request
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import time


class CrawlWorker(QThread):
    status_updated = pyqtSignal(str)
    progress_updated = pyqtSignal(int)
    progress_max_updated = pyqtSignal(int)
    total_progress_updated = pyqtSignal(int, int) # current, total
    finished = pyqtSignal()

    def __init__(self, urls, folder):
        super().__init__()
        self.urls = urls
        self.base_folder = folder
        self.is_running = True

    def run(self):
        driver = None
        is_batch = len(self.urls) > 1
        try:
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
            
            self.status_updated.emit('브라우저에서 직접 로그인해주세요...')
            driver.get("https://arca.live/u/login?goto=%2F")

            long_wait = WebDriverWait(driver, 3600)
            long_wait.until(EC.url_to_be("https://arca.live/"))
            self.status_updated.emit('로그인 확인됨.')

            total_urls = len(self.urls)
            for idx, url in enumerate(self.urls):
                if not self.is_running:
                    self.status_updated.emit("크롤링 중지됨.")
                    break
                
                self.total_progress_updated.emit(idx + 1, total_urls)
                current_folder = self.base_folder
                if is_batch:
                    timestamp = time.strftime("%Y-%m-%d-%H-%M-%S")
                    folder_name = f"{timestamp}"
                    current_folder = os.path.join(self.base_folder, folder_name)
                    
                    # Handle folder name collision
                    counter = 1
                    while os.path.exists(current_folder):
                        current_folder = os.path.join(self.base_folder, f"{folder_name}_({counter})")
                        counter += 1
                    os.makedirs(current_folder)

                self.status_updated.emit(f"크롤링 페이지로 이동: {url}")
                driver.get(url)
                time.sleep(1)

                a_tags = driver.find_elements(By.XPATH, "/html/body/div[2]/div[3]/article/div/div[2]/div[4]//a")
                total_images = len(a_tags)
                
                if total_images == 0:
                    self.status_updated.emit(f"{url} 에서 다운로드할 이미지를 찾지 못했습니다.")
                    continue

                self.progress_max_updated.emit(total_images)
                self.progress_updated.emit(0)

                num_digits = len(str(total_images))
                hrefs = [a.get_attribute("href") for a in a_tags]

                count = 0
                for i, href in enumerate(hrefs):
                    if not self.is_running:
                        break

                    try:
                        driver.get(href)
                        img_tag = driver.find_element(By.TAG_NAME, "img")
                        img_url = img_tag.get_attribute("src")

                        if img_url:
                            img_data = requests.get(img_url).content
                            filename = f"{str(i+1).zfill(num_digits)}.jpg"
                            filepath = os.path.join(current_folder, filename)

                            with open(filepath, "wb") as f:
                                f.write(img_data)

                            self.status_updated.emit(f"{i+1}/{total_images} 이미지 다운로드 완료: {filepath}")
                            count += 1
                            self.progress_updated.emit(count)

                    except Exception as e:
                        self.status_updated.emit(f"이미지 다운로드 실패: {e}")
                
                if not self.is_running:
                    break

        except Exception as e:
            self.status_updated.emit(f"오류 발생: {e}")

        finally:
            if driver:
                driver.quit()
            self.finished.emit()

    def stop(self):
        self.is_running = False

class MyApp(QMainWindow):

    def __init__(self):
        super().__init__()
        self.worker = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Image Crawler")

        # URL 입력창
        self.url_label = QLabel("URL:", self)
        self.url_label.move(20, 20)
        self.url_input = QLineEdit(self)
        self.url_input.move(80, 20)
        self.url_input.resize(200, 20)

        self.url_file_btn = QPushButton('파일 선택', self)
        self.url_file_btn.move(290, 20)
        self.url_file_btn.clicked.connect(self.select_url_file)

        # 폴더 선택창
        self.folder_label = QLabel("저장 폴더:", self)
        self.folder_label.move(20, 60)
        self.folder_path = QLineEdit(self)
        self.folder_path.move(80, 60)
        self.folder_path.resize(200, 20)
        self.folder_path.setReadOnly(True)

        self.folder_btn = QPushButton("폴더 선택", self)
        self.folder_btn.move(290, 60)
        self.folder_btn.clicked.connect(self.select_folder)

        self.crawl_btn = QPushButton('크롤링 시작', self)
        self.crawl_btn.move(20, 100)
        self.crawl_btn.clicked.connect(self.crawl)

        self.stop_btn = QPushButton('중지', self)
        self.stop_btn.move(110, 100)
        self.stop_btn.clicked.connect(self.stop_crawl)
        self.stop_btn.setEnabled(False)

        self.clear_btn = QPushButton('지우기', self)
        self.clear_btn.move(200, 100)
        self.clear_btn.clicked.connect(self.clear_status)

        self.status_text = QTextEdit(self)
        self.status_text.move(20, 140)
        self.status_text.resize(360, 150)
        self.status_text.setReadOnly(True)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.move(20, 300)
        self.progress_bar.resize(360, 20)

        self.total_progress_label = QLabel("", self)
        self.total_progress_label.move(20, 325)

        self.setGeometry(300, 300, 400, 380)
        self.show()

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "폴더 선택")
        if folder:
            self.folder_path.setText(folder)

    def select_url_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'URL 텍스트 파일 선택', '', 'Text files (*.txt)')
        if fname:
            self.url_input.setText(fname)

    def clear_status(self):
        self.status_text.clear()

    def stop_crawl(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()

    def crawl(self):
        url_input_text = self.url_input.text()
        folder = self.folder_path.text()

        if not url_input_text or not folder:
            self.status_text.append('URL(또는 txt파일)과 저장 폴더를 모두 입력해주세요.')
            return

        urls = []
        if os.path.exists(url_input_text) and url_input_text.lower().endswith('.txt'):
            try:
                with open(url_input_text, 'r') as f:
                    urls = [line.strip() for line in f if line.strip()]
                if not urls:
                    self.status_text.append('txt 파일이 비어있습니다.')
                    return
            except Exception as e:
                self.status_text.append(f'txt 파일을 읽는 중 오류 발생: {e}')
                return
        else:
            urls.append(url_input_text)

        # Check for existing image files (only for single URL case)
        if len(urls) == 1:
            image_extensions = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp')
            has_images = False
            if os.path.exists(folder):
                for filename in os.listdir(folder):
                    if filename.lower().endswith(image_extensions):
                        has_images = True
                        break
            
            if has_images:
                reply = QMessageBox.warning(self, '경고', 
                    "선택한 폴더에 이미 이미지 파일이 존재합니다. 덮어쓸 수 있습니다.\n계속하시겠습니까?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

                if reply == QMessageBox.No:
                    self.status_text.append("작업이 취소되었습니다.")
                    return

        self.crawl_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_text.setText("크롤링을 시작합니다...")
        self.progress_bar.setValue(0)
        self.total_progress_label.setText("")
        
        self.worker = CrawlWorker(urls=urls, folder=folder)
        self.worker.status_updated.connect(self.update_status)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.progress_max_updated.connect(self.update_progress_max)
        self.worker.total_progress_updated.connect(self.update_total_progress)
        self.worker.finished.connect(self.on_crawl_finished)
        self.worker.start()

    def update_status(self, message):
        self.status_text.append(message)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_progress_max(self, value):
        self.progress_bar.setMaximum(value)

    def update_total_progress(self, current, total):
        if total > 1:
            self.total_progress_label.setText(f'{total}개 중 {current}번째 URL 처리 중...')

    def on_crawl_finished(self):
        self.crawl_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.total_progress_label.setText("완료")
        if not self.worker.is_running: # Check if stopped manually
             self.status_text.append("작업이 사용자에 의해 중지되었습니다.")
        else:
             self.status_text.append("모든 작업이 완료되었습니다.")
        self.worker = None



if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = MyApp()
    sys.exit(app.exec_())
