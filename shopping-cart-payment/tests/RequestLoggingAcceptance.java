import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.lang.reflect.Proxy;
import java.util.HashMap;
import java.util.Map;
import org.slf4j.LoggerFactory;
import org.springframework.web.filter.OncePerRequestFilter;

/** Uses real filter and Logback from the exact live baseline image. */
public class RequestLoggingAcceptance {
    public static void main(String[] args) throws Exception {
        Class<?> type = Class.forName(args[0]);
        OncePerRequestFilter filter = (OncePerRequestFilter) type.getConstructor().newInstance();
        Logger logger = (Logger) LoggerFactory.getLogger(type);
        ListAppender<ILoggingEvent> events = new ListAppender<>();
        events.start();
        logger.addAppender(events);
        Map<String, Object> attributes = new HashMap<>();
        HttpServletRequest request = (HttpServletRequest) Proxy.newProxyInstance(
                RequestLoggingAcceptance.class.getClassLoader(), new Class[]{HttpServletRequest.class},
                (obj, method, values) -> switch (method.getName()) {
                    case "getMethod" -> "GET";
                    case "getAttribute" -> attributes.get(values[0]);
                    case "setAttribute" -> { attributes.put((String) values[0], values[1]); yield null; }
                    case "removeAttribute" -> { attributes.remove(values[0]); yield null; }
                    case "getDispatcherType" -> jakarta.servlet.DispatcherType.REQUEST;
                    case "isAsyncStarted" -> false;
                    default -> throw new AssertionError("Private request data read: " + method.getName());
                });
        HttpServletResponse response = (HttpServletResponse) Proxy.newProxyInstance(
                RequestLoggingAcceptance.class.getClassLoader(), new Class[]{HttpServletResponse.class},
                (obj, method, values) -> {
                    if (method.getName().equals("getStatus")) return 200;
                    throw new AssertionError("Response changed by logger: " + method.getName());
                });
        filter.doFilter(request, response, (req, res) -> {});
        ServletException expected = new ServletException("sensitive exception detail");
        try {
            filter.doFilter(request, response, (req, res) -> { throw expected; });
            throw new AssertionError("Exception swallowed");
        } catch (ServletException actual) {
            if (actual != expected) throw new AssertionError("Exception replaced");
        }
        if (events.list.size() != 2) throw new AssertionError("Expected one log per dispatch");
        if (!events.list.get(0).getFormattedMessage().contains("outcome=returned")) throw new AssertionError("Success absent");
        if (!events.list.get(1).getFormattedMessage().contains("outcome=exception")) throw new AssertionError("Failure absent");
        if (events.list.stream().anyMatch(e -> e.getFormattedMessage().contains("sensitive"))) throw new AssertionError("Private data logged");
        System.out.println("PASS: success, exception propagation, one log per request, no private data read/response changes.");
    }
}
