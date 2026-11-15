package com.culturalmuseum.auth.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "Request payload for user authentication / login")
public class LoginRequest {

    @Schema(description = "Username or registered email", example = "john_doe", requiredMode = Schema.RequiredMode.REQUIRED)
    private String username;

    @Schema(description = "Account password", example = "P@ssword123", requiredMode = Schema.RequiredMode.REQUIRED)
    private String password;

    public LoginRequest() {
    }

    public LoginRequest(String username, String password) {
        this.username = username;
        this.password = password;
    }

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
}
