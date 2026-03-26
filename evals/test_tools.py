"""Tools 层单元测试

测试覆盖:
- file_reader: 文件读取、目录列表、路径安全校验
- code_search: 代码搜索、符号搜索
- tree_parser: AST 结构解析
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.tools.file_reader import list_directory, read_file, read_key_files
from src.tools.code_search import search_code, search_symbol


@pytest.fixture
def sample_repo(tmp_path: Path) -> str:
    """创建一个用于测试的样例 Java 仓库。"""
    src = tmp_path / "src" / "main" / "java" / "com" / "example"
    src.mkdir(parents=True)

    (src / "OrderService.java").write_text("""\
package com.example;

public class OrderService {
    private final PayService payService;

    public OrderService(PayService payService) {
        this.payService = payService;
    }

    public String createOrder(String userId, double amount) {
        validate(userId, amount);
        String orderId = generateOrderId();
        payService.processPayment(orderId, amount);
        return orderId;
    }

    private void validate(String userId, double amount) {
        if (userId == null || amount <= 0) {
            throw new IllegalArgumentException("Invalid params");
        }
    }

    private String generateOrderId() {
        return "ORD-" + System.currentTimeMillis();
    }
}
""")

    (src / "PayService.java").write_text("""\
package com.example;

public interface PayService {
    void processPayment(String orderId, double amount);
}
""")

    (tmp_path / "pom.xml").write_text("""\
<project>
    <groupId>com.example</groupId>
    <artifactId>sample</artifactId>
    <version>1.0.0</version>
</project>
""")

    (tmp_path / "README.md").write_text("# Sample Project\nA test project.")
    return str(tmp_path)


class TestFileReader:
    def test_read_file_success(self, sample_repo: str) -> None:
        result = read_file.invoke({
            "file_path": "src/main/java/com/example/OrderService.java",
            "repo_path": sample_repo,
        })
        assert "class OrderService" in result
        assert "createOrder" in result

    def test_read_file_with_line_range(self, sample_repo: str) -> None:
        result = read_file.invoke({
            "file_path": "src/main/java/com/example/OrderService.java",
            "repo_path": sample_repo,
            "start_line": 1,
            "end_line": 5,
        })
        assert "package com.example" in result

    def test_read_file_not_found(self, sample_repo: str) -> None:
        result = read_file.invoke({
            "file_path": "nonexistent.java",
            "repo_path": sample_repo,
        })
        assert "不存在" in result or "错误" in result or "Error" in result

    def test_read_file_path_traversal_blocked(self, sample_repo: str) -> None:
        with pytest.raises(Exception, match="不在仓库范围"):
            read_file.invoke({
                "file_path": "../../../etc/passwd",
                "repo_path": sample_repo,
            })

    def test_list_directory(self, sample_repo: str) -> None:
        result = list_directory.invoke({
            "dir_path": sample_repo,
            "repo_path": sample_repo,
            "max_depth": 2,
        })
        assert "src" in result

    def test_read_key_files(self, sample_repo: str) -> None:
        result = read_key_files.invoke({"repo_path": sample_repo})
        assert "README" in result or "pom.xml" in result


class TestCodeSearch:
    def test_search_code_found(self, sample_repo: str) -> None:
        result = search_code.invoke({
            "pattern": "createOrder",
            "repo_path": sample_repo,
            "max_results": 10,
        })
        assert "createOrder" in result

    def test_search_code_not_found(self, sample_repo: str) -> None:
        result = search_code.invoke({
            "pattern": "nonExistentMethodXyz",
            "repo_path": sample_repo,
            "max_results": 5,
        })
        assert "未找到" in result or "0" in result

    def test_search_symbol_class(self, sample_repo: str) -> None:
        result = search_symbol.invoke({
            "name": "OrderService",
            "repo_path": sample_repo,
            "symbol_type": "class",
        })
        assert "OrderService" in result

    def test_search_symbol_method(self, sample_repo: str) -> None:
        result = search_symbol.invoke({
            "name": "createOrder",
            "repo_path": sample_repo,
            "symbol_type": "method",
        })
        assert "createOrder" in result


class TestTreeParser:
    def test_parse_file_structure(self, sample_repo: str) -> None:
        from src.tools.tree_parser import parse_file_structure

        result = parse_file_structure.invoke({
            "file_path": "src/main/java/com/example/OrderService.java",
            "repo_path": sample_repo,
        })
        assert "OrderService" in result
        assert "createOrder" in result

    def test_extract_method_body(self, sample_repo: str) -> None:
        from src.tools.tree_parser import extract_method_body

        result = extract_method_body.invoke({
            "file_path": "src/main/java/com/example/OrderService.java",
            "method_name": "createOrder",
            "repo_path": sample_repo,
        })
        assert "createOrder" in result

    def test_find_method_calls(self, sample_repo: str) -> None:
        from src.tools.tree_parser import find_method_calls

        result = find_method_calls.invoke({
            "file_path": "src/main/java/com/example/OrderService.java",
            "method_name": "createOrder",
            "repo_path": sample_repo,
        })
        assert "validate" in result or "processPayment" in result or "generateOrderId" in result
