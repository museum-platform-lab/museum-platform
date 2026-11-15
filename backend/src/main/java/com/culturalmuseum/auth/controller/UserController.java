package com.culturalmuseum.auth.controller;

import com.culturalmuseum.auth.dto.request.LoginRequest;
import com.culturalmuseum.auth.dto.request.UserCreationRequest;
import com.culturalmuseum.auth.dto.request.UserUpdateRequest;
import com.culturalmuseum.auth.dto.response.LoginResponse;
import com.culturalmuseum.auth.dto.response.UserResponse;
import com.culturalmuseum.auth.service.UserService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/auth")
@Tag(name = "Authentication & Users", description = "Endpoints for user management and authentication")
public class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    // 1. REGISTER / CREATE USER
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @Operation(summary = "Register / Create a new user", description = "Creates a new user account with BCrypt password hashing")
    @ApiResponses(value = {
            @ApiResponse(responseCode = "201", description = "User created successfully"),
            @ApiResponse(responseCode = "400", description = "Invalid request payload"),
            @ApiResponse(responseCode = "409", description = "Username or Email already exists")
    })
    public UserResponse createUser(@RequestBody UserCreationRequest request) {
        return userService.createUser(request);
    }

    // 2. LOGIN USER
    @PostMapping("/login")
    @Operation(summary = "User Login", description = "Authenticates user credentials using BCrypt verification")
    @ApiResponses(value = {
            @ApiResponse(responseCode = "200", description = "Login successful"),
            @ApiResponse(responseCode = "400", description = "Invalid credentials format"),
            @ApiResponse(responseCode = "401", description = "Invalid username/email or password")
    })
    public LoginResponse login(@RequestBody LoginRequest request) {
        return userService.login(request);
    }

    // 3. READ ALL USERS (ACTIVE ONLY)
    @GetMapping
    @Operation(summary = "Get all active users", description = "Retrieves a list of all active users in the system")
    @ApiResponses(value = {
            @ApiResponse(responseCode = "200", description = "List of active users retrieved successfully")
    })
    public List<UserResponse> getAllUsers() {
        return userService.getAllUsers();
    }

    // 4. READ USER BY ID
    @GetMapping("/{id}")
    @Operation(summary = "Get user by ID", description = "Retrieves detailed information of an active user by their unique ID")
    @ApiResponses(value = {
            @ApiResponse(responseCode = "200", description = "User found"),
            @ApiResponse(responseCode = "404", description = "User not found or has been deactivated")
    })
    public UserResponse getUserById(
            @Parameter(description = "ID of the user to be retrieved", example = "1")
            @PathVariable Long id) {
        return userService.getUserById(id);
    }

    // 5. UPDATE USER
    @PutMapping("/{id}")
    @Operation(summary = "Update user details", description = "Updates information of an existing active user")
    @ApiResponses(value = {
            @ApiResponse(responseCode = "200", description = "User updated successfully"),
            @ApiResponse(responseCode = "400", description = "Invalid request payload"),
            @ApiResponse(responseCode = "404", description = "User not found or has been deactivated")
    })
    public UserResponse updateUser(
            @Parameter(description = "ID of the user to be updated", example = "1")
            @PathVariable Long id,
            @RequestBody UserUpdateRequest request) {
        return userService.updateUser(id, request);
    }

    // 6. SOFT DELETE USER
    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @Operation(summary = "Soft delete user", description = "Deactivates a user by setting status to deleted (status = 0)")
    @ApiResponses(value = {
            @ApiResponse(responseCode = "204", description = "User deactivated successfully (No Content)"),
            @ApiResponse(responseCode = "404", description = "User not found or already deactivated")
    })
    public void deleteUser(
            @Parameter(description = "ID of the user to be deleted", example = "1")
            @PathVariable Long id) {
        userService.deleteUser(id);
    }
}
