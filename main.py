# run.py
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "exam_system.asgi:application",  # Путь к ASGI-приложению в формате "module:variable"
        host="0.0.0.0",                   # Слушать все входящие соединения
        port=8000,                        # Порт
        reload=True,                      # Автоперезагрузка (для разработки)
        log_level="info"                  # Уровень логирования
    )