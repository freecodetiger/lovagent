import asyncio
import inspect


def pytest_pyfunc_call(pyfuncitem):
    test_func = pyfuncitem.obj
    if inspect.iscoroutinefunction(test_func):
        signature = inspect.signature(test_func)
        kwargs = {
            name: value
            for name, value in pyfuncitem.funcargs.items()
            if name in signature.parameters
        }
        asyncio.run(test_func(**kwargs))
        return True
    return None
