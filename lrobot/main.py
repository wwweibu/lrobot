# 项目主入口
import asyncio
import tracemalloc
from web.backend.app import server_runner,app
from secret import secret
from logic import backup_mysql,backup_mongo
from message.handler.msg_pool import MsgPool
from config import config, future, loggers, init_mysql, add_scheduler, log_writer, config_watcher
from message.adapter import refresh_tokens, LR232_router,  WECHAT_router, LR5921_router,bili_msg_get


async def start():
    """初始化函数"""
    loop = asyncio.get_running_loop()
    future.init(loop)  # future 管理器记录主循环
    await init_mysql()


async def stop():
    """清理函数"""
    pass


async def scheduler():
    """定时任务"""
    await asyncio.sleep(5)
    asyncio.create_task(add_scheduler(backup_mysql, interval=86400))  # 备份 Mysql
    asyncio.create_task(add_scheduler(backup_mongo, interval=86400))  # 备份 Mongo
    asyncio.create_task(add_scheduler(MsgPool.clean_messages,86400,interval=86400)) # 消息池清理
    #asyncio.create_task(add_scheduler(check_network, interval=300))  # 检查网络
    #asyncio.create_task(add_scheduler(check_system, interval=60))  # 检查系统


async def init_LR232():
    app.include_router(LR232_router, prefix=secret("/LR232"))


async def init_LR5921():
    app.include_router(LR5921_router, prefix=secret("/LR5921"))


async def init_WECHAT():
    app.include_router(WECHAT_router, prefix=secret("/WECHAT"))


async def init_QQAPP():
    #app.include_router(QQAPP_router, prefix=secret("/QQAPP"))
    pass

async def init_BILI():
    await bili_msg_get()
    asyncio.create_task(add_scheduler(bili_msg_get, 20,interval=20))


def set_tasks():
    """生成任务列表"""
    tasks = [
        config_watcher(),  # 配置自动更新、自动写入
        log_writer(),  # 日志记录器
        scheduler(),  # 定时任务
        MsgPool.process_messages(),  # 消息处理

    ]
    platform_config = {
        "LR232": ["LR232_ID", "LR232_SECRET"],
        "LR5921": ["LR5921_ID"],
        "WECHAT": ["WECHAT_ID", "WECHAT_SECRET"],
        "QQAPP": ["QQAPP_ID", "QQAPP_SECRET"],
        "BILI": ["BILI_SESSDATA","BILI_JCT"]
    }  # 平台配置参数

    platform_list = [
        name for name, keys in platform_config.items()
        if all(config[k] for k in keys)
    ]  # 激活的平台列表

    tasks.extend([
        globals()[f"init_{name}"]()  # 调用 init_LR232 等函数
        for name in platform_list
    ])

    tasks.append(refresh_tokens(platform_list))  # 令牌刷新任务
    tasks.append(server_runner())  # 服务器运行

    return tasks


async def main():
    """代码主入口，运行所有任务"""
    await start()
    tasks = set_tasks()
    print(tasks)

    try:
        results = await asyncio.gather(
            *tasks, return_exceptions=True
        )  # 某任务出现异常不阻塞其他任务
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                loggers["system"].error(
                    f"任务{i}异常 -> {result}", extra={"event": "运行日志"}
                )
    finally:
        await stop()


if __name__ == "__main__":
    asyncio.run(main())
