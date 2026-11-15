package com.culturalmuseum.auth.dto.response;

import com.culturalmuseum.auth.entity.User;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.LocalDate;
import java.time.OffsetDateTime;

@Schema(description = "User response payload (excluding sensitive credentials)")
public class UserResponse {

    @Schema(description = "User unique ID", example = "1")
    private Long id;

    @Schema(description = "Unique username", example = "john_doe")
    private String username;

    @Schema(description = "User email address", example = "john.doe@example.com")
    private String email;

    @Schema(description = "Contact phone number", example = "0987654321")
    private String phone;

    @Schema(description = "First name", example = "John")
    private String firstName;

    @Schema(description = "Last name", example = "Doe")
    private String lastName;

    @Schema(description = "Full name", example = "Doe John")
    private String fullName;

    @Schema(description = "Avatar Image URL", example = "https://example.com/avatar.jpg")
    private String avatarUrl;

    @Schema(description = "Date of birth (YYYY-MM-DD)", example = "1995-08-20")
    private LocalDate dob;
    
    @Schema(description = "Method used to register (LOCAL, GOOGLE, etc.)", example = "LOCAL")
    private String authProvider;

    @Schema(description = "User role level (1: User, 2: Staff, 3: Admin)", example = "1")
    private Integer role;

    @Schema(description = "Creation timestamp")
    private OffsetDateTime createdAt;

    @Schema(description = "Last updated timestamp")
    private OffsetDateTime updatedAt;

    public UserResponse() {
    }

    // Static mapper method from Entity to DTO
    public static UserResponse fromEntity(User user) {
        if (user == null) {
            return null;
        }

        UserResponse response = new UserResponse();
        response.setId(user.getId());
        response.setUsername(user.getUsername());
        response.setEmail(user.getEmail());
        response.setPhone(user.getPhone());
        response.setFirstName(user.getFirstName());
        response.setLastName(user.getLastName());
        response.setAvatarUrl(user.getAvatarUrl());
        response.setAuthProvider(user.getAuthProvider());

        // Construct full name if firstName / lastName exist
        String first = user.getFirstName() != null ? user.getFirstName() : "";
        String last = user.getLastName() != null ? user.getLastName() : "";
        response.setFullName((last + " " + first).trim());

        response.setDob(user.getDob());
        response.setRole(user.getRole());
        response.setCreatedAt(user.getCreatedAt());
        response.setUpdatedAt(user.getUpdatedAt());

        return response;
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getUsername() {
        return username;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    public String getEmail() {
        return email;
    }

    public void setEmail(String email) {
        this.email = email;
    }

    public String getPhone() {
        return phone;
    }

    public void setPhone(String phone) {
        this.phone = phone;
    }

    public String getFirstName() {
        return firstName;
    }

    public void setFirstName(String firstName) {
        this.firstName = firstName;
    }

    public String getLastName() {
        return lastName;
    }

    public void setLastName(String lastName) {
        this.lastName = lastName;
    }

    public String getFullName() {
        return fullName;
    }

    public void setFullName(String fullName) {
        this.fullName = fullName;
    }

    public String getAvatarUrl() {
        return avatarUrl;
    }

    public void setAvatarUrl(String avatarUrl) {
        this.avatarUrl = avatarUrl;
    }

    public String getAuthProvider() {
        return authProvider;
    }

    public void setAuthProvider(String authProvider) {
        this.authProvider = authProvider;
    }

    public LocalDate getDob() {
        return dob;
    }

    public void setDob(LocalDate dob) {
        this.dob = dob;
    }

    public Integer getRole() {
        return role;
    }

    public void setRole(Integer role) {
        this.role = role;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(OffsetDateTime createdAt) {
        this.createdAt = createdAt;
    }

    public OffsetDateTime getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(OffsetDateTime updatedAt) {
        this.updatedAt = updatedAt;
    }
}
