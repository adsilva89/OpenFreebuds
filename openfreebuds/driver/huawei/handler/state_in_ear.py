import json
from openfreebuds.driver.huawei.driver.generic import OfbDriverHandlerHuawei
from openfreebuds.driver.huawei.package import HuaweiSppPackage


class OfbHuaweiStateInEarHandler(OfbDriverHandlerHuawei):
    """
    TWS in-ear state detection handler
    """

    handler_id = "tws_in_ear"
    commands = [b'+\x03', b'+%', b'+,']  # 2b03, 2b25, 2b2c

    async def on_init(self):
        await self.driver.put_property("state", "in_ear", "false")

    async def on_package(self, package: HuaweiSppPackage):
        # Processar diferentes comandos
        if package.command_id == b'+\x03':  # 2b03 - comando original
            value = package.find_param(8, 9)
            if len(value) == 1:
                await self.driver.put_property("state", "in_ear", json.dumps(value[0] == 1))
        elif package.command_id == b'+%':  # 2b25 - comando in_ear para FreeBuds Pro 4
            param1 = package.find_param(1)
            param2 = package.find_param(2)
            if len(param1) >= 1 and len(param2) >= 1:
                # Ambos fones no ouvido se param1=1 e param2=1
                in_ear = param1[0] == 1 and param2[0] == 1
                await self.driver.put_property("state", "in_ear", json.dumps(in_ear))
        elif package.command_id == b'+,':  # 2b2c - outro comando in_ear
            param1 = package.find_param(1)
            if len(param1) >= 1:
                # param1=0 significa fone removido
                in_ear = param1[0] != 0
                await self.driver.put_property("state", "in_ear", json.dumps(in_ear))
