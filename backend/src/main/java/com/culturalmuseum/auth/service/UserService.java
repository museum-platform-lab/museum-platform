package com.culturalmuseum.auth.service;

import com.culturalmuseum.auth.dto.request.LoginRequest;
import com.culturalmuseum.auth.dto.request.UserCreationRequest;
import com.culturalmuseum.auth.dto.request.UserUpdateRequest;
import com.culturalmuseum.auth.dto.response.LoginResponse;
import com.culturalmuseum.auth.dto.response.UserResponse;
import com.culturalmuseum.auth.entity.User;
import com.culturalmuseum.auth.repository.UserRepository;
import com.culturalmuseum.auth.util.JwtTokenProvider;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class UserService {

    private static final int STATUS_ACTIVE = 1;
    private static final int STATUS_DELETED = 0;

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenProvider jwtTokenProvider;

    public UserService(UserRepository userRepository, 
                       PasswordEncoder passwordEncoder, 
                       JwtTokenProvider jwtTokenProvider) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtTokenProvider = jwtTokenProvider;
    }

    // Helper: Tìm entity User active dùng trong nội bộ Service
    public User findActiveUserById(Long id) {
        return userRepository.findByIdAndStatus(id, STATUS_ACTIVE)
                .orElseThrow(() -> new RuntimeException("User not found or deactivated with id: " + id));
    }

    // 1. CREATE USER (ĐĂNG KÝ VỚI MẬT KHẨU ĐÃ MÃ HÓA BCRYPT)
    public UserResponse createUser(UserCreationRequest request) {
        if (userRepository.existsByUsernameAndStatus(request.getUsername(), STATUS_ACTIVE)) {
            throw new RuntimeException("Username already exists: " + request.getUsername());
        }

        if (request.getEmail() != null && !request.getEmail().isBlank()) {
            if (userRepository.existsByEmailAndStatus(request.getEmail(), STATUS_ACTIVE)) {
                throw new RuntimeException("Email already registered: " + request.getEmail());
            }
        }

        User user = new User();
        user.setUsername(request.getUsername());
        
        // MÃ HÓA BCRYPT: Mật khẩu thô (plaintext) được băm an toàn trước khi vào DB
        user.setPassword(passwordEncoder.encode(request.getPassword()));

        user.setEmail(request.getEmail());
        user.setPhone(request.getPhone());
        user.setFirstName(request.getFirstName());
        user.setLastName(request.getLastName());
        user.setDob(request.getDob());
        user.setAvatarUrl(request.getAvatarUrl());
        
        // Nếu role truyền vào là null thì set mặc định = 1 (Người dùng thường)
        user.setRole(request.getRole() != null ? request.getRole() : 1);
        
        user.setAuthProvider("LOCAL"); // Mặc định là đăng ký thường
        user.setStatus(STATUS_ACTIVE);

        User savedUser = userRepository.save(user);
        return UserResponse.fromEntity(savedUser);
    }

    // 2. LOGIN (ĐĂNG NHẬP, SO KHỚP BCRYPT & SINH TOKEN JWT)
    public LoginResponse login(LoginRequest request) {
        String loginIdentifier = request.getUsername();

        // Cho phép đăng nhập linh hoạt bằng username hoặc email
        User user = userRepository.findByUsernameAndStatusOrEmailAndStatus(
                loginIdentifier, STATUS_ACTIVE, loginIdentifier, STATUS_ACTIVE)
                .orElseThrow(() -> new RuntimeException("Invalid username or password"));

        // Kiểm tra khớp mật khẩu bằng BCrypt
        if (!passwordEncoder.matches(request.getPassword(), user.getPassword())) {
            throw new RuntimeException("Invalid username or password");
        }

        // Tạo JWT Token có thời hạn 24h
        String token = jwtTokenProvider.generateToken(user);

        return LoginResponse.success(user, token);
    }

    // 3. READ ALL USERS (Active only -> Trả về List<UserResponse>)
    public List<UserResponse> getAllUsers() {
        return userRepository.findAllByStatus(STATUS_ACTIVE)
                .stream()
                .map(UserResponse::fromEntity)
                .toList();
    }

    // 4. READ USER BY ID -> Trả về UserResponse
    public UserResponse getUserById(Long id) {
        User user = findActiveUserById(id);
        return UserResponse.fromEntity(user);
    }

    // 5. UPDATE USER -> Trả về UserResponse
    public UserResponse updateUser(Long id, UserUpdateRequest request) {
        User user = findActiveUserById(id);

        if (request.getPassword() != null && !request.getPassword().isBlank()) {
            // Nếu người dùng đổi mật khẩu, băm lại mật khẩu mới
            user.setPassword(passwordEncoder.encode(request.getPassword()));
        }
        if (request.getEmail() != null) {
            user.setEmail(request.getEmail());
        }
        if (request.getPhone() != null) {
            user.setPhone(request.getPhone());
        }
        if (request.getFirstName() != null) {
            user.setFirstName(request.getFirstName());
        }
        if (request.getLastName() != null) {
            user.setLastName(request.getLastName());
        }
        if (request.getAvatarUrl() != null) {
            user.setAvatarUrl(request.getAvatarUrl());
        }
        if (request.getDob() != null) {
            user.setDob(request.getDob());
        }
        if (request.getRole() != null) {
            user.setRole(request.getRole());
        }

        User updatedUser = userRepository.save(user);
        return UserResponse.fromEntity(updatedUser);
    }

    // 6. SOFT DELETE USER
    public void deleteUser(Long id) {
        User user = findActiveUserById(id);
        user.setStatus(STATUS_DELETED);
        userRepository.save(user);
    }
}
