package com.culturalmuseum.auth.repository;

import com.culturalmuseum.auth.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface UserRepository extends JpaRepository<User, Long> {

    // Tìm user theo username và status (Active = 1)
    Optional<User> findByUsernameAndStatus(String username, Integer status);

    // Tìm user theo username HOẶC email (khi còn active) để hỗ trợ đăng nhập linh hoạt
    Optional<User> findByUsernameAndStatusOrEmailAndStatus(String username, Integer status1, String email, Integer status2);

    // Kiểm tra username đã tồn tại trong các user đang active chưa
    boolean existsByUsernameAndStatus(String username, Integer status);

    // Kiểm tra email đã tồn tại chưa
    boolean existsByEmailAndStatus(String email, Integer status);

    // Lấy toàn bộ danh sách user theo trạng thái
    List<User> findAllByStatus(Integer status);

    // Tìm user theo id và trạng thái còn active
    Optional<User> findByIdAndStatus(Long id, Integer status);
}
