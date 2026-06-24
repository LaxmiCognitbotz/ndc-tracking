import axios from "axios";
import { toast } from "sonner";

const api = axios.create({
  // baseURL can be added here if needed, currently using relative paths like /api/v1/...
});

// Response interceptor for API calls
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Determine the error message
    const message = 
      error.response?.data?.message || 
      error.response?.data?.detail || 
      error.message || 
      "An unexpected API error occurred.";
      
    // Display global error toast
    toast.error(`Error: ${message}`, {
      description: error.response?.status ? `Status code: ${error.response.status}` : "Network error",
    });

    return Promise.reject(error);
  }
);

export default api;
