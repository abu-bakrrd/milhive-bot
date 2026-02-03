#!/延ash
# Скрипт автоматической настройки для Ubuntu 22.04

# Остановить при ошибке
set -e

echo "🚀 Начинаем установку..."

# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка зависимостей
sudo apt install -y python3 python3-pip python3-venv git libgl1

# Создание директории проекта (если вдруг нет)
mkdir -p ~/milhive_bot
cd ~/milhive_bot

# Создание виртуального окружения
python3 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install --upgrade pip
pip install -r requirements.txt

# Превью загрузки модели для rembg
python3 -c "from rembg import remove; import numpy as np; remove(np.zeros((1,1,3), dtype=np.uint8))" || true

# Установка сервиса
echo "⚙️ Настройка системного сервиса..."
if [ -f "milhive_bot.service" ]; then
    sudo cp milhive_bot.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable milhive_bot
    
    if [ -f ".env" ]; then
        echo "🚀 Запуск бота..."
        sudo systemctl start milhive_bot
        echo "✅ Сервис запущен!"
    else
        echo "⚠️ Файл .env не найден. Заполните его и выполните: sudo systemctl start milhive_bot"
    fi
else
    echo "❌ Файл milhive_bot.service не найден!"
fi

echo "✨ Установка полностью завершена!"
