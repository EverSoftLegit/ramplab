// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Synthetic six-decimal token for local RampLab exercises only.
contract MockUSDC {
    string public constant name = "RampLab Synthetic USD Coin";
    string public constant symbol = "rlUSDC";
    uint8 public constant decimals = 6;

    address public owner;
    uint256 public totalSupply;
    mapping(address => bool) public minters;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event MinterUpdated(address indexed minter, bool allowed);
    event Burn(address indexed from, uint256 value);

    modifier onlyOwner() {
        require(msg.sender == owner, "not owner");
        _;
    }

    modifier onlyMinter() {
        require(minters[msg.sender], "not minter");
        _;
    }

    constructor() {
        owner = msg.sender;
        minters[msg.sender] = true;
    }

    function setMinter(address minter, bool allowed) external onlyOwner {
        require(minter != address(0), "zero minter");
        minters[minter] = allowed;
        emit MinterUpdated(minter, allowed);
    }

    function mint(address to, uint256 amount) external onlyMinter {
        require(to != address(0) && amount > 0, "invalid mint");
        totalSupply += amount;
        balanceOf[to] += amount;
        emit Transfer(address(0), to, amount);
    }

    /// @notice Burn redeemed synthetic tokens from circulation.
    /// @dev Lab off-ramp settlement: an authorised ramp operator removes tokens
    /// after settling fiat off-chain. A production redemption would instead rely
    /// on a customer-signed transfer into custody, not operator-side burning.
    function burn(address from, uint256 amount) external onlyMinter {
        require(from != address(0) && amount > 0, "invalid burn");
        require(balanceOf[from] >= amount, "insufficient token balance");
        balanceOf[from] -= amount;
        totalSupply -= amount;
        emit Transfer(from, address(0), amount);
        emit Burn(from, amount);
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        _transfer(msg.sender, to, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        uint256 permitted = allowance[from][msg.sender];
        require(permitted >= amount, "allowance exceeded");
        allowance[from][msg.sender] = permitted - amount;
        _transfer(from, to, amount);
        return true;
    }

    function _transfer(address from, address to, uint256 amount) internal {
        require(to != address(0) && amount > 0, "invalid transfer");
        require(balanceOf[from] >= amount, "insufficient token balance");
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        emit Transfer(from, to, amount);
    }
}
