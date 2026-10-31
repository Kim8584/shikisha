// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script, console} from "forge-std/Script.sol";
import {Registry} from "../Registry.sol";

contract DeployScript is Script {
    function run() external returns (Registry) {
        uint256 deployerPrivateKey = vm.envOr(
            "PRIVATE_KEY",
            uint256(0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80) // Default Anvil key #0
        );

        vm.startBroadcast(deployerPrivateKey);

        Registry registry = new Registry();
        console.log("Registry deployed at:", address(registry));

        vm.stopBroadcast();
        return registry;
    }
}
