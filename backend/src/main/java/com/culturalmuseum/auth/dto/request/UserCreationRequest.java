package com.culturalmuseum.auth.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;
import java.time.LocalDate;

@Schema(description = "Request payload for user registration")
public class UserCreationRequest {

    @Schema(description = "User unique name", example = "john_doe", requiredMode = Schema.RequiredMode.REQUIRED)
    private String username;

    @Schema(description = "User password", example = "P@ssword123", requiredMode = Schema.RequiredMode.REQUIRED)
    private String password;

    @Schema(description = "Email address for login and notifications", example = "john.doe@example.com")
    private String email;

    @Schema(description = "Contact phone number", example = "0987654321")
    private String phone;

    @Schema(description = "First name", example = "John")
    private String firstName;

    @Schema(description = "Last name", example = "Doe")
    private String lastName;

    @Schema(description = "Date of birth (YYYY-MM-DD)", example = "1995-08-20")
    private LocalDate dob;
    
    @Schema(description = "URL to the user's avatar image", example = "https://example.com/avatar.jpg")
    private String avatarUrl;

    @Schema(description = "User role level (1: User, 2: Staff, 3: Admin)", example = "1")
    private Integer role;

    public String getUsername() {
        return username;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    public String getPassword() {
        return password;
    }

    public void setPassword(String password) {
        this.password = password;
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

    public LocalDate getDob() {
        return dob;
    }

    public void setDob(LocalDate dob) {
        this.dob = dob;
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
