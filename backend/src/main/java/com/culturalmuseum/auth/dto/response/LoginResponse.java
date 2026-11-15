package com.culturalmuseum.auth.dto.response;

import com.culturalmuseum.auth.entity.User;
import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "Response payload after successful authentication / login")
public class LoginResponse {

    @Schema(description = "Status message", example = "Login successful")
    private String message;

    @Schema(description = "JWT Access Token for authorization", example = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
    private String token;

    @Schema(description = "Token type format", example = "Bearer")
    private String tokenType = "Bearer";

    @Schema(description = "User unique ID", example = "1")
    private Long id;

    @Schema(description = "Username", example = "john_doe")
    private String username;

    @Schema(description = "User email", example = "john.doe@example.com")
    private String email;

    @Schema(description = "Full name", example = "Doe John")
    private String fullName;

    @Schema(description = "Avatar URL", example = "https://example.com/avatar.jpg")
    private String avatarUrl;

    @Schema(description = "User role level (1: User, 2: Staff, 3: Admin)", example = "1")
    private Integer role;

    public LoginResponse() {
    }

    // Static mapper method with Token
    public static LoginResponse success(User user, String token) {
        LoginResponse response = new LoginResponse();
        response.setMessage("Login successful");
        response.setToken(token);
        response.setTokenType("Bearer");
        response.setId(user.getId());
        response.setUsername(user.getUsername());
        response.setEmail(user.getEmail());

        String first = user.getFirstName() != null ? user.getFirstName() : "";
        String last = user.getLastName() != null ? user.getLastName() : "";
        String fullName = (last + " " + first).trim();
        response.setFullName(!fullName.isEmpty() ? fullName : user.getUsername());

        response.setAvatarUrl(user.getAvatarUrl());
        response.setRole(user.getRole());
        return response;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public String getToken() {
        return token;
    }

    public void setToken(String token) {
        this.token = token;
    }

    public String getTokenType() {
        return tokenType;
    }

    public void setTokenType(String tokenType) {
        this.tokenType = tokenType;
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

    public Integer getRole() {
        return role;
    }

    public void setRole(Integer role) {
        this.role = role;
    }
}
